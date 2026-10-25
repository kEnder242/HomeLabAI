import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from infra.cumulative_telemetry import log_telemetry_event


def test_log_telemetry_event_ground_truth(monkeypatch):
    """Verify log_telemetry_event accurately records physical tokens and calculated throughput."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stream_path = os.path.join(tmpdir, "live_usage_stream.jsonl")
        cumulative_path = os.path.join(tmpdir, "cumulative_tokens.json")
        monkeypatch.setattr("infra.cumulative_telemetry.DATA_DIR", tmpdir)
        monkeypatch.setattr("infra.cumulative_telemetry.STREAM_JSONL_PATH", stream_path)
        monkeypatch.setattr("infra.cumulative_telemetry.CUMULATIVE_JSON_PATH", cumulative_path)

        # Emit an event with 120 tokens over 2.5 seconds (48.0 tok/s)
        log_telemetry_event(
            source="Web Intercom (Pinky (Response))",
            task_title="Mice Turn: Pinky (Response)",
            seat="Linux 2080ti",
            provider="VLLM",
            model="Llama-3.2-3B-AWQ",
            tokens_generated=120,
            duration_seconds=2.5,
            raw_throughput_tok_s=48.0,
        )

        assert os.path.exists(stream_path)
        with open(stream_path, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 1
        rec = lines[0]
        assert rec["seat"] == "Linux 2080ti"
        assert rec["tokens_generated"] == 120
        assert rec["duration_seconds"] == 2.5
        assert rec["throughput_tok_s"] == 48.0
        assert rec["throughput_tok_s"] != 35.0
        assert rec["tier"] == "sovereign_local"


@pytest.mark.asyncio
async def test_router_handle_telemetry_ingest_wiring(monkeypatch):
    """Verify router.handle_telemetry_ingest parses real loader tokens and duration, invoking log_telemetry_event."""
    from v5.foyer.router import FoyerRouter

    router = FoyerRouter()
    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={
        "node": "pinky",
        "request_id": "test_req_123",
        "ttft_ms": 250.0,
        "total_tokens": 150,
        "duration_s": 3.0,
        "engine_type": "VLLM",
        "model": "Llama-3.2-3B-AWQ",
    })

    logged_events = []
    def fake_log_telemetry_event(**kwargs):
        logged_events.append(kwargs)

    monkeypatch.setattr("infra.cumulative_telemetry.log_telemetry_event", fake_log_telemetry_event)

    resp = await router.handle_telemetry_ingest(mock_request)
    assert resp.status == 200
    assert len(logged_events) == 1
    ev = logged_events[0]
    assert ev["tokens_generated"] == 150
    assert ev["duration_seconds"] == 3.0
    assert ev["raw_throughput_tok_s"] == 50.0
    assert ev["seat"] == "Linux 2080ti"
    assert ev["source"] == "Web Intercom (Pinky (Response))"
