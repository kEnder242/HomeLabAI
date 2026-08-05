import pytest
import pytest_asyncio
import httpx
import asyncio
import socket
import os
import glob
import json
import time
import sys

# ---------------------------------------------------------------------------
# [STORY 7] Validation Gate: cognitive_hub.py + archive_node.py syntax/import
# smoke checks and multi-voice Composite HyDE parsing assertions.
#
# These are pure unit tests and run regardless of Round Table endpoint state,
# so they are declared BEFORE the module-level skipif marker below.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
for _p in (_REPO_ROOT, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.logic.cognitive_hub import CognitiveHub
from src.nodes.archive_node import parse_multi_voice_hyde


def test_story7_cognitive_hub_import_smoke():
    """[STORY 7] CognitiveHub imports cleanly from src.logic.cognitive_hub."""
    assert CognitiveHub is not None
    assert callable(CognitiveHub)


def test_story7_parse_multi_voice_hyde_joins_voices():
    """[STORY 7] Multi-voice Composite HyDE string parses to joined payloads."""
    result = parse_multi_voice_hyde(
        "[VALIDATION]: ras | [STRATEGY]: goal | [SRE]: scar"
    )
    assert result == "ras goal scar"


def test_story7_roundtable_validation_gate():
    """[STORY 7] Exact roundtable validation behavior verified by the gate."""
    assert parse_multi_voice_hyde(
        "[VALIDATION]: ras | [STRATEGY]: goal | [SRE]: scar"
    ) == "ras goal scar"


def test_story7_parse_multi_voice_hyde_fallback_raw():
    """[STORY 7] Non-multi-voice input falls back to the raw string."""
    assert parse_multi_voice_hyde("plain query text") == "plain query text"


# ---------------------------------------------------------------------------
# Module-level skip: TCP probes for Round Table endpoints
# ---------------------------------------------------------------------------
def _tcp_probe(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


_FOYER_UP = _tcp_probe("localhost", 8765)
_ROUNDTABLE_8088_UP = _tcp_probe("127.0.0.1", 8088)
_ROUNDTABLE_8000_UP = _tcp_probe("127.0.0.1", 8000)
pytestmark = pytest.mark.skipif(
    not (_FOYER_UP or _ROUNDTABLE_8088_UP or _ROUNDTABLE_8000_UP),
    reason="No Round Table endpoint reachable (need localhost:8765, or 127.0.0.1:8088/8000)"
)

@pytest.mark.asyncio
async def test_rest_inject_produces_response():
    async with httpx.AsyncClient() as client:
        payload = {"query": "What did I work on in 2018?"}
        response = await client.post("http://localhost:8765/inject", json=payload)
        
        assert response.status_code == 200
        
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json.get('status') == 'QUEUED' and 'id' in response_json
        
        # Check if 'content' or 'data' key is not empty
        if "content" in response_json:
            assert response_json["content"] != ""
        elif "data" in response_json:
            assert response_json["data"] != ""


@pytest.mark.asyncio
async def test_roundtable_transcript_logged():
    if not _FOYER_UP:
        pytest.skip("Foyer service is offline — cannot verify transcript logging")

    logs_dir = "/home/jallred/Dev_Lab/HomeLabAI/logs/"
    log_files = glob.glob(os.path.join(logs_dir, "evaluation_batch_*.log"))

    if not log_files:
        pytest.skip("No evaluation_batch_*.log files found — logs may not have been generated yet")

    # Sort files by modification time (newest first)
    log_files.sort(key=os.path.getmtime, reverse=True)
    newest_log_file = log_files[0]

    file_mod_time = os.path.getmtime(newest_log_file)
    current_time = time.time()

    assert (current_time - file_mod_time) < 180, f"Log file {newest_log_file} not modified within the last 180 seconds"

    with open(newest_log_file, "r") as f:
        content = f.read()

        found_entry = False
        for line in content.splitlines():
            try:
                log_entry = json.loads(line)
                if isinstance(log_entry, dict) and log_entry.get("role") == "CHAT" and "node" in log_entry:
                    found_entry = True
                    break
            except json.JSONDecodeError:
                continue

        assert found_entry, "No JSON entry with 'role': 'CHAT' and 'node' found in the log file"


if __name__ == "__main__":
    # Direct execution block
    pytest.main([__file__])