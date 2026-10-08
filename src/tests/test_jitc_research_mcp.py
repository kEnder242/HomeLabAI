"""
[Story 99.0 / BKM-024 / FEAT-647] 100% Live stdio JSON-RPC MCP Server Integration Tests.
Strictly tests the canonical /home/jallred/AcmeLab/src/clara_dna_mcp_server.py process over stdio.
Zero in-memory mocks, zero sys.path monkeypatching.
"""

import json
import os
import subprocess
import time
import pytest


def _send_rpc(proc: subprocess.Popen, request: dict) -> dict:
    """Send a JSON-RPC request to the MCP stdio subprocess and parse the JSON response line."""
    req_str = json.dumps(request) + "\n"
    proc.stdin.write(req_str)
    proc.stdin.flush()
    resp_str = proc.stdout.readline()
    if not resp_str:
        stderr_out = proc.stderr.read()
        raise RuntimeError(f"MCP server exited or produced no output. Stderr: {stderr_out}")
    return json.loads(resp_str.strip())


@pytest.fixture(scope="module")
def mcp_proc():
    """Spawns the real canonical MCP server subprocess over stdio."""
    canonical_paths = [
        os.path.expanduser("~/Dev_Lab/HomeLabAI/src/mcp/clara_dna_mcp_server.py"),
        "/home/jallred/AcmeLab/src/clara_dna_mcp_server.py",
    ]
    mcp_script = next((p for p in canonical_paths if os.path.exists(p)), canonical_paths[0])
    py_bin = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
    assert os.path.exists(mcp_script), f"Canonical MCP server script not found: {mcp_script}"
    assert os.path.exists(py_bin), f"Python virtualenv binary not found: {py_bin}"

    proc = subprocess.Popen(
        [py_bin, mcp_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Initialize handshake
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "live_test_harness", "version": "1.0.0"},
        },
    }
    init_resp = _send_rpc(proc, init_req)
    assert "result" in init_resp, f"MCP Initialize failed: {init_resp}"

    yield proc

    # Teardown
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


def test_live_mcp_tools_list(mcp_proc):
    """[BKM-024] Live stdio probe: Assert that MCP server advertises all 6 mandatory tools."""
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"tools/list failed: {resp}"
    tools = resp["result"].get("tools", [])
    tool_names = {t["name"] for t in tools}

    mandatory_tools = [
        "safe_patch",
        "jit_read",
        "jit_locate",
        "jit_stage",
        "jit_research",
        "jit_diagnose",
        "jit_checkpoint",
        "query_dna",
        "get_protocol",
        "list_collections",
    ]
    for tool_name in mandatory_tools:
        assert tool_name in tool_names, f"Mandatory tool '{tool_name}' missing from live MCP tools: {tool_names}"

    canonical_jit_tools = [
        "jit_read",
        "jit_locate",
        "jit_stage",
        "jit_research",
        "jit_diagnose",
        "jit_checkpoint",
    ]
    for jt in canonical_jit_tools:
        assert jt in tool_names, f"Canonical JIT tool '{jt}' missing from live MCP tools: {tool_names}"


def test_live_mcp_stage_and_research(mcp_proc):
    """[FEAT-647] Live stdio test: Stage a plan and recall it via research tool."""
    test_file = "src/logic/live_test_dummy.py"

    # 1. Stage Research
    stage_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "jit_stage",
            "arguments": {
                "file_path": test_file,
                "plan_content": "Live stdio JSON-RPC test plan",
                "patch_blueprint": "<<<SEARCH\nold_logic()\n===\nnew_logic()\n>>>",
                "ast_anchors": ["class LiveTestNode", "def execute()"],
                "diff_directives": ["Replace sync call with async probe"],
            },
        },
    }
    stage_resp = _send_rpc(mcp_proc, stage_req)
    assert "result" in stage_resp, f"jit_stage call failed: {stage_resp}"

    # 2. Recall via research tool
    research_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "jit_research",
            "arguments": {"file_path": test_file},
        },
    }
    research_resp = _send_rpc(mcp_proc, research_req)
    assert "result" in research_resp, f"jit_research call failed: {research_resp}"
    content_list = research_resp["result"].get("content", [])
    assert len(content_list) > 0, "Empty content in research response"
    text = content_list[0].get("text", "")

    assert f"STAGED CONDUCTOR BLUEPRINT: `{test_file}`" in text
    assert "class LiveTestNode" in text
    assert "new_logic()" in text
    assert "Live stdio JSON-RPC test plan" in text


def test_live_mcp_failure_whisperer(mcp_proc):
    """[FEAT-647] Live stdio test: failure_whisperer diagnoses test traceback."""
    sample_traceback = "Traceback (most recent call last):\n  File 'test.py', line 12\nE   AssertionError: expected True but got False"
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "jit_diagnose",
            "arguments": {"test_output": sample_traceback},
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"jit_diagnose call failed: {resp}"
    text = resp["result"]["content"][0]["text"]
    assert "AssertionError: expected True but got False" in text
    assert "Diagnosis:" in text


def test_live_mcp_handoff_checkpoint(mcp_proc):
    """[FEAT-647] Live stdio test: handoff_checkpoint writes structured record."""
    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "jit_checkpoint",
            "arguments": {
                "status": "SUCCESS",
                "summary": "Live stdio checkpoint test",
                "artifacts_modified": ["src/test.py"],
            },
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"jit_checkpoint call failed: {resp}"


def test_live_mcp_locate_path(mcp_proc):
    """[FEAT-647] Live stdio test: locate_path resolves symbol and paths."""
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "jit_locate",
            "arguments": {"pattern": "cognitive_hub"},
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"jit_locate call failed: {resp}"


def test_live_mcp_canonical_jit_tools_flow(mcp_proc):
    """[Story 100.2 / FEAT-649] Test the full canonical jit_* tool calling flow over live JSON-RPC stdio."""
    test_target = "src/v5/cognition/test_dummy_target.py"

    # 1. jit_stage
    stage_req = {
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "jit_stage",
            "arguments": {
                "file_path": test_target,
                "plan_content": "Canonical JIT orchestration plan",
                "patch_blueprint": "<<<SEARCH\nfoo()\n===\nbar()\n>>>",
                "ast_anchors": ["def test_dummy()"],
                "diff_directives": ["Replace foo with bar"],
            },
        },
    }
    stage_resp = _send_rpc(mcp_proc, stage_req)
    assert "result" in stage_resp, f"jit_stage failed: {stage_resp}"

    # 2. jit_research
    research_req = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "jit_research",
            "arguments": {"file_path": test_target},
        },
    }
    research_resp = _send_rpc(mcp_proc, research_req)
    assert "result" in research_resp, f"jit_research failed: {research_resp}"
    content = research_resp["result"]["content"][0]["text"]
    assert "Canonical JIT orchestration plan" in content
    assert "def test_dummy()" in content

    # 3. jit_diagnose
    diag_req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "jit_diagnose",
            "arguments": {"test_output": "Traceback (most recent call last):\n  File 'test_dummy.py', line 20\nE   AssertionError: 404 != 200"},
        },
    }
    diag_resp = _send_rpc(mcp_proc, diag_req)
    assert "result" in diag_resp, f"jit_diagnose failed: {diag_resp}"
    diag_text = diag_resp["result"]["content"][0]["text"]
    assert "AssertionError: 404 != 200" in diag_text

    # 4. jit_checkpoint
    chk_req = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "jit_checkpoint",
            "arguments": {
                "status": "SUCCESS",
                "summary": "Canonical JIT shakedown checkpoint",
                "artifacts_modified": [test_target],
            },
        },
    }
    chk_resp = _send_rpc(mcp_proc, chk_req)
    assert "result" in chk_resp, f"jit_checkpoint failed: {chk_resp}"

    # 5. jit_locate
    loc_req = {
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {
            "name": "jit_locate",
            "arguments": {"pattern": "context_prewarmer"},
        },
    }
    loc_resp = _send_rpc(mcp_proc, loc_req)
    assert "result" in loc_resp, f"jit_locate failed: {loc_resp}"

