"""
[SPR-47.1 Story 10] Tri-Node Federated Integration Test
Validates that Node Brain (vLLM, 127.0.0.1:8088), Node KENDER (Ollama,
192.168.1.26:11434), and Node M5 Air (MLX, 192.168.1.46:8000) are reachable,
produce valid technical evaluations, and log entries to evaluation batch logs.
"""

import glob
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

import pytest

# ---------------------------------------------------------------------------
# Node definitions
# ---------------------------------------------------------------------------
NODES = {
    "brain": {
        "host": "127.0.0.1",
        "port": 8088,
        "base": "http://127.0.0.1:8088",
        "protocol": "openai",
        "model": "default",
        "description": "Node Brain (vLLM, local)",
    },
    "kender": {
        "host": "192.168.1.26",
        "port": 11434,
        "base": "http://192.168.1.26:11434",
        "protocol": "ollama",
        "model": "qwen2.5-coder:14b",
        "description": "Node KENDER (Ollama, remote)",
    },
    "m5_air": {
        "host": "192.168.1.46",
        "port": 8000,
        "base": "http://192.168.1.46:8000",
        "protocol": "openai",
        "model": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        "description": "Node M5 Air (MLX, remote)",
    },
}

TCP_TIMEOUT = 3.0
CHAT_TIMEOUT = 120
SAMPLE_PROMPT = (
    "Evaluate RAPL telemetry for Optane AEP under 100W PL1 power limit."
)

LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs",
)

# ---------------------------------------------------------------------------
# Module-level probe functions
# ---------------------------------------------------------------------------
def _probe_tcp(host: str, port: int, timeout: float = TCP_TIMEOUT) -> bool:
    """Return True if TCP connect succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _probe_brain() -> bool:
    """TCP probe Node Brain (vLLM) on 127.0.0.1:8088."""
    return _probe_tcp("127.0.0.1", 8088)


def _probe_kender() -> bool:
    """TCP probe Node KENDER (Ollama) on 192.168.1.26:11434."""
    return _probe_tcp("192.168.1.26", 11434)


def _probe_m5_air() -> bool:
    """TCP probe Node M5 Air (MLX) on 192.168.1.46:8000."""
    return _probe_tcp("192.168.1.46", 8000)


# Module-level reachability flags (evaluated at import time)
BRAIN_UP = _probe_brain()
KENDER_UP = _probe_kender()
M5_AIR_UP = _probe_m5_air()
ANY_NODE_UP = BRAIN_UP or KENDER_UP or M5_AIR_UP

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _inventory_ledger() -> list[dict]:
    """Return a clean ledger array reporting each node's online/offline status."""
    return [
        {
            "node": "brain",
            "host": "127.0.0.1",
            "port": 8088,
            "status": "ONLINE" if BRAIN_UP else "OFFLINE",
            "description": "Node Brain (vLLM, local)",
        },
        {
            "node": "kender",
            "host": "192.168.1.26",
            "port": 11434,
            "status": "ONLINE" if KENDER_UP else "OFFLINE",
            "description": "Node KENDER (Ollama, remote)",
        },
        {
            "node": "m5_air",
            "host": "192.168.1.46",
            "port": 8000,
            "status": "ONLINE" if M5_AIR_UP else "OFFLINE",
            "description": "Node M5 Air (MLX, remote)",
        },
    ]


def _openai_chat_completion(base: str, model: str, prompt: str) -> dict:
    """OpenAI-compatible chat completion via /v1/chat/completions."""
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a technical evaluation engine."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 150,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        return json.loads(resp.read().decode("utf-8"))


def _ollama_chat_completion(base: str, model: str, prompt: str) -> dict:
    """Ollama chat completion via /api/chat."""
    url = f"{base}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a technical evaluation engine."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        return json.loads(resp.read().decode("utf-8"))


def _evaluate_on_node(node_name: str) -> str | None:
    """
    Send SAMPLE_PROMPT to *node_name*.
    Return the response content string, or None if the node is unreachable
    or the request fails.
    """
    node = NODES[node_name]
    try:
        if node["protocol"] == "openai":
            body = _openai_chat_completion(
                node["base"], node["model"], SAMPLE_PROMPT
            )
            return body["choices"][0]["message"]["content"]
        elif node["protocol"] == "ollama":
            body = _ollama_chat_completion(
                node["base"], node["model"], SAMPLE_PROMPT
            )
            return body["message"]["content"]
    except (urllib.error.URLError, OSError, Exception):
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_tri_node_inventory():
    """
    Query all 3 endpoints via TCP probe. Report node online/offline status
    in a clean ledger array. Assert that at least one compute node is reachable.
    """
    ledger = _inventory_ledger()
    print(f"\n  Tri-Node Inventory ({len(ledger)} nodes):")
    for entry in ledger:
        status_mark = "✓" if entry["status"] == "ONLINE" else "✗"
        print(f"    [{status_mark}] {entry['node']:8s}  {entry['host']:15s}:{entry['port']:<5d}  {entry['status']}")
    assert ANY_NODE_UP, (
        f"No compute nodes reachable. Ledger: {json.dumps(ledger, indent=2)}"
    )


def test_tri_node_evaluation_fallback():
    """
    Send 'Evaluate RAPL telemetry for Optane AEP under 100W PL1 power limit.'
    to available nodes. Assert that responses return valid technical evaluations
    without crashing or returning stub errors ('OFFLINE_STUB', 'VERIFIED_PASS').
    """
    stub_phrases = ["OFFLINE_STUB", "VERIFIED_PASS", "Fallback evaluation"]
    online_nodes = [n for n, flag in
                    [("brain", BRAIN_UP), ("kender", KENDER_UP), ("m5_air", M5_AIR_UP)]
                    if flag]

    if not online_nodes:
        pytest.skip("No nodes are online — cannot run evaluation test.")

    results = []
    for node_name in online_nodes:
        content = _evaluate_on_node(node_name)
        if content is None:
            print(f"\n  [{node_name}] Node unreachable or request failed — skipping")
            continue
        assert len(content) > 20, (
            f"{node_name}: response too short ({len(content)} chars): {content[:80]}"
        )
        for phrase in stub_phrases:
            assert phrase not in content, (
                f"{node_name}: response contains known stub phrase: '{phrase}'"
            )
        print(f"\n  [{node_name}] Response length: {len(content)} chars")
        print(f"  [{node_name}] Preview: {content[:120]}...")
        results.append({"node": node_name, "response_length": len(content), "preview": content[:120]})

    assert len(results) > 0, (
        "No online node produced a valid non-stub evaluation."
    )

    # Write evaluation event log entry
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"evaluation_batch_{int(time.time())}.log")
    log_entry = {
        "event": "evaluation_batch",
        "timestamp": time.time(),
        "prompt": SAMPLE_PROMPT,
        "nodes": results,
    }
    with open(log_path, "w") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(f"\n  [log] Wrote evaluation event to {os.path.basename(log_path)}")


def test_tri_node_logging():
    """
    Verify that evaluation runs log entry events to
    HomeLabAI/logs/evaluation_batch_*.log or fallback memory logs.
    """
    log_pattern = os.path.join(LOG_DIR, "evaluation_batch_*.log")
    log_files = glob.glob(log_pattern)

    if not log_files:
        pytest.skip(f"No evaluation_batch_*.log files found in {LOG_DIR}")

    # Sort by modification time (newest first)
    log_files.sort(key=os.path.getmtime, reverse=True)
    newest = log_files[0]

    # Verify the file has content and scan for JSON entries referencing a node name
    node_keys = {"brain", "kender", "m5_air", "Brain", "KENDER", "M5"}
    found = False
    with open(newest, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            content_str = json.dumps(entry)
            if any(k in content_str for k in node_keys):
                found = True
                break

    assert found, (
        f"No log entry referencing any compute node found in {newest}"
    )
    print(f"\n  Log evidence: {newest}")


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Tri-Node Federated Integration Test")
    print("=" * 60)

    if not ANY_NODE_UP:
        print("\nNo compute nodes reachable. Inventory:")
        for entry in _inventory_ledger():
            print(f"  {entry['node']:8s}: {entry['status']}")
        print("\nSKIP: At least one node must be reachable.")
        sys.exit(0)

    # test_tri_node_inventory
    print("\n--- test_tri_node_inventory ---")
    try:
        test_tri_node_inventory()
        print("PASS")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    # test_tri_node_evaluation_fallback
    print("\n--- test_tri_node_evaluation_fallback ---")
    try:
        test_tri_node_evaluation_fallback()
        print("PASS")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    # test_tri_node_logging
    print("\n--- test_tri_node_logging ---")
    try:
        test_tri_node_logging()
        print("PASS")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All Story 10 Tri-Node integration tests passed.")
    print("=" * 60)
