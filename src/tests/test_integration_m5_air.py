"""
[SPR-47.1 Story 9] M5 Air MLX Integration Test
Validates that the M5 Air MLX endpoint at 192.168.1.46:8000 responds
to model listing and chat completion requests with valid responses.
"""
import json
import socket
import sys
import urllib.error
import urllib.request

import pytest

# ---------------------------------------------------------------------------
# Module-level skip: TCP probe 192.168.1.46:8000
# ---------------------------------------------------------------------------
def _m5_air_reachable(host="192.168.1.46", port=8000, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


M5_AIR_UP = _m5_air_reachable()
pytestmark = pytest.mark.skipif(
    not M5_AIR_UP, reason="M5 Air MLX not running on 192.168.1.46:8000"
)

M5_AIR_BASE = "http://192.168.1.46:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _chat_completion_result():
    """Perform a chat completion and return the parsed response body."""
    url = f"{M5_AIR_BASE}/v1/chat/completions"
    payload = {
        "model": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        "messages": [
            {"role": "system", "content": "You are an MLX Judge."},
            {
                "role": "user",
                "content": (
                    "Evaluate the performance of 16-channel Optane memory "
                    "controller architecture in 2 sentences."
                ),
            },
        ],
        "max_tokens": 150,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, timeout=120) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_m5_air_mlx_reachable():
    """GET /v1/models returns 200 with at least one model in data."""
    url = f"{M5_AIR_BASE}/v1/models"
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        body = json.loads(resp.read().decode("utf-8"))
        assert "data" in body, "Response must contain 'data' key"
        assert len(body["data"]) >= 1, "Must have at least one model"


def test_m5_air_chat_completion():
    """POST /v1/chat/completions returns a valid completion."""
    body = _chat_completion_result()
    assert "choices" in body, "Response must contain 'choices'"
    assert len(body["choices"]) > 0, "Must have at least one choice"
    content = body["choices"][0]["message"]["content"]
    assert len(content) > 20, f"Content too short ({len(content)} chars)"


def test_m5_air_not_stub():
    """Assert chat completion response is not a stub/fallback."""
    body = _chat_completion_result()
    content = body["choices"][0]["message"]["content"]
    assert "OFFLINE_STUB" not in content
    assert "VERIFIED_PASS" not in content
    assert "Fallback evaluation" not in content


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not M5_AIR_UP:
        print("SKIP: M5 Air MLX not running on 192.168.1.46:8000")
        sys.exit(0)

    test_m5_air_mlx_reachable()
    print("PASS: test_m5_air_mlx_reachable")
    test_m5_air_chat_completion()
    print("PASS: test_m5_air_chat_completion")
    test_m5_air_not_stub()
    print("PASS: test_m5_air_not_stub")
    print("All Story 9 M5 Air MLX integration tests passed.")
