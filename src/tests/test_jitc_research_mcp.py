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
    mcp_script = "/home/jallred/AcmeLab/src/clara_dna_mcp_server.py"
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
        "read",
        "safe_patch",
        "locate_grounding",
        "stage_research",
        "research",
        "failure_whisperer",
        "handoff_checkpoint",
        "locate_path",
    ]
    for tool_name in mandatory_tools:
        assert tool_name in tool_names, f"Mandatory tool '{tool_name}' missing from live MCP tools: {tool_names}"


def test_live_mcp_stage_and_research(mcp_proc):
    """[FEAT-647] Live stdio test: Stage a plan and recall it via research tool."""
    test_file = "src/logic/live_test_dummy.py"

    # 1. Stage Research
    stage_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "stage_research",
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
    assert "result" in stage_resp, f"stage_research call failed: {stage_resp}"

    # 2. Recall via research tool
    research_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "research",
            "arguments": {"file_path": test_file},
        },
    }
    research_resp = _send_rpc(mcp_proc, research_req)
    assert "result" in research_resp, f"research call failed: {research_resp}"
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
            "name": "failure_whisperer",
            "arguments": {"test_output": sample_traceback},
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"failure_whisperer call failed: {resp}"
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
            "name": "handoff_checkpoint",
            "arguments": {
                "status": "SUCCESS",
                "summary": "Live stdio checkpoint test",
                "artifacts_modified": ["src/test.py"],
            },
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"handoff_checkpoint call failed: {resp}"


def test_live_mcp_locate_path(mcp_proc):
    """[FEAT-647] Live stdio test: locate_path resolves symbol and paths."""
    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "locate_path",
            "arguments": {"pattern": "cognitive_hub"},
        },
    }
    resp = _send_rpc(mcp_proc, req)
    assert "result" in resp, f"locate_path call failed: {resp}"
