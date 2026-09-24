"""
[FEAT-607 / LAB-110] Unit Test: Dream Cycle Telemetry & Accountability Verification
Tests that DreamManager emits structured non-zero telemetry, handles cabinet fallback,
and adheres to BKM-062 Zero-Work Exit Invariant.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from dream_cycle import DreamManager


@pytest.fixture
def mock_archive():
    archive = AsyncMock()
    return archive


@pytest.mark.asyncio
async def test_dream_cycle_stream_synthesis(mock_archive):
    """Verify standard dream cycle with chaotic memories produces PASS telemetry."""
    # Mock stream dump with 3 memories
    stream_resp = MagicMock()
    stream_resp.content = [MagicMock(text=json.dumps({
        "documents": ["Memory 1", "Memory 2", "Memory 3"],
        "ids": ["mem_1", "mem_2", "mem_3"]
    }))]
    mock_archive.call_tool.side_effect = [
        stream_resp, # get_stream_dump
        MagicMock()   # dream
    ]

    manager = DreamManager(mock_archive)
    # Monkey-patch remote_brain_think to return fast summary
    import dream_cycle
    orig_think = dream_cycle.remote_brain_think
    dream_cycle.remote_brain_think = AsyncMock(return_value="Synthesized Diamond Wisdom")

    try:
        telemetry = await manager.run_cycle()
        assert telemetry is not None
        assert telemetry["status"] == "PASS"
        assert telemetry["turns_synthesized"] == 3
        assert telemetry["items_refined"] == 0
        assert telemetry["duration_seconds"] >= 0.0
        assert "timestamp" in telemetry
    finally:
        dream_cycle.remote_brain_think = orig_think


@pytest.mark.asyncio
async def test_dream_cycle_zero_work_fails(mock_archive):
    """Verify BKM-062 Zero-Work Exit Rule: zero turns and zero refinements must NOT be PASS."""
    # Mock empty stream and cabinet with no files
    stream_resp = MagicMock()
    stream_resp.content = [MagicMock(text=json.dumps({"documents": [], "ids": []}))]
    cab_resp = MagicMock()
    cab_resp.content = [MagicMock(text=json.dumps([]))]

    mock_archive.call_tool.side_effect = [
        stream_resp, # get_stream_dump
        cab_resp     # list_cabinet
    ]

    manager = DreamManager(mock_archive)
    telemetry = await manager.run_cycle()
    assert telemetry is not None
    assert telemetry["status"] in ("FAIL", "DEGRADED")
    assert telemetry["turns_synthesized"] == 0
    assert telemetry["items_refined"] == 0
    assert telemetry["error"] is not None
