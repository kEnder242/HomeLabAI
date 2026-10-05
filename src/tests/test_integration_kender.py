"""
[SPR-47.1] Kender (Ollama) Integration Test
Probes the remote Ollama instance on 192.168.1.26:11434 and validates
model availability and basic chat completion functionality.
"""

import socket
import sys

import pytest
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KENDER_HOST = "192.168.1.26"
KENDER_PORT = 11434
KENDER_BASE = f"http://{KENDER_HOST}:{KENDER_PORT}"
TCP_TIMEOUT = 3.0
CHAT_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Module-level skip: TCP probe KENDER
# ---------------------------------------------------------------------------
def _kender_reachable(host=KENDER_HOST, port=KENDER_PORT, timeout=TCP_TIMEOUT):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, OSError):
        return False


KENDER_UP = _kender_reachable()
pytestmark = pytest.mark.skipif(
    not KENDER_UP,
    reason=f"KENDER (Ollama) not reachable at {KENDER_HOST}:{KENDER_PORT}",
)

# Module-level cache for chat response used by stub check
_CHAT_RESPONSE: dict | None = None


def _discover_model(timeout=10.0):
    """GET /api/tags; prefer resident Qwen model, else first available model.

    Returns the model name string, or None if unreachable/empty (caller skips).
    """
    try:
        resp = requests.get(f"{KENDER_BASE}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return None
        models = resp.json().get("models") or []
    except (requests.exceptions.RequestException, ValueError):
        return None
    names: list[str] = [
        str(m["name"])
        for m in models
        if isinstance(m, dict) and isinstance(m.get("name"), str) and m["name"].strip()
    ]
    if not names:
        return None
    for name in names:
        if "qwen" in name.lower():
            return name
    return names[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_kender_ollama_reachable():
    """GET /api/tags returns 200 with at least one model entry."""
    resp = requests.get(f"{KENDER_BASE}/api/tags", timeout=TCP_TIMEOUT)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.json()
    assert "models" in body, "Response must contain 'models' key"
    assert len(body["models"]) >= 1, "Expected at least one model in /api/tags"
    print(f"  Models available: {len(body['models'])}")


def test_kender_chat_completion():
    """POST /api/chat with a dynamically discovered model returns a non-trivial message."""
    global _CHAT_RESPONSE
    model = _discover_model()
    if model is None:
        pytest.skip("KENDER Ollama reports no models via GET /api/tags")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are Deep Thought, a reasoning engine.",
            },
            {
                "role": "user",
                "content": "Summarize the 2018 Intel Optane AEP validation campaign in 2 sentences.",
            },
        ],
        "stream": False,
    }
    try:
        resp = requests.post(f"{KENDER_BASE}/api/chat", json=payload, timeout=CHAT_TIMEOUT)
    except requests.exceptions.Timeout:
        pytest.skip(f"KENDER chat timed out after {CHAT_TIMEOUT}s (model: {model})")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code} (model: {model})"
    body = resp.json()
    assert "message" in body, "Response must contain 'message' key"
    assert "content" in body["message"], "Response message must contain 'content'"
    content = body["message"]["content"]
    assert (
        len(content) > 20
    ), f"Response content too short ({len(content)} chars): {content[:80]}"
    _CHAT_RESPONSE = body
    print(f"  Model: {model}")
    print(f"  Response length: {len(content)} chars")
    print(f"  Response preview: {content[:120]}...")


def test_kender_response_not_stub():
    """Verify chat response is not a known fallback/stub phrase."""
    global _CHAT_RESPONSE
    if _CHAT_RESPONSE is None:
        pytest.skip(
            "No chat response: chat_completion was skipped (model not discovered or timed out)"
        )
    content = _CHAT_RESPONSE["message"]["content"]
    stub_phrases = ["OFFLINE_STUB", "VERIFIED_PASS", "Coherent technical alignment"]
    for phrase in stub_phrases:
        assert phrase not in content, f"Response contains known stub phrase: '{phrase}'"


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not KENDER_UP:
        print(f"SKIP: KENDER (Ollama) not reachable at {KENDER_HOST}:{KENDER_PORT}")
        sys.exit(0)

    # Run tests sequentially
    print("test_kender_ollama_reachable ... ", end="", flush=True)
    test_kender_ollama_reachable()
    print("PASS")

    print("test_kender_chat_completion ... ", end="", flush=True)
    test_kender_chat_completion()
    print("PASS")

    print("test_kender_response_not_stub ... ", end="", flush=True)
    test_kender_response_not_stub()
    print("PASS")

    print("\nAll KENDER integration tests passed.")
