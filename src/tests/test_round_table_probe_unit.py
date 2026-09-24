"""
[FEAT-608 / LAB-110] Unit Test: Round Table Accountability Probe Verification
Hermetic unit tests for probe_round_table_accountability.py with mocked HTTP responses.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from infra.probe_round_table_accountability import (
    probe_greeting_latency,
    probe_deliberation_circuit,
    run_round_table_accountability_probe
)


@pytest.mark.asyncio
async def test_greeting_latency_pass():
    """Verify greeting probe succeeds when Foyer returns 200 OPERATIONAL."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"state": "OPERATIONAL"})
    session.get.return_value.__aenter__.return_value = mock_resp

    result = await probe_greeting_latency(session, "http://127.0.0.1:8765")
    assert result["status"] == "PASS"
    assert result["foyer_state"] == "OPERATIONAL"
    assert result["latency_ms"] >= 0.0
    assert result["error"] is None


@pytest.mark.asyncio
async def test_deliberation_circuit_pass():
    """Verify deliberation circuit probe succeeds when Foyer inject returns 200 QUEUED."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "status": "QUEUED",
        "id": "evt_test123",
        "routing": "SYSTEM_HEALTH",
        "critic_score": 0.98
    })
    session.post.return_value.__aenter__.return_value = mock_resp

    result = await probe_deliberation_circuit(session, "http://127.0.0.1:8765")
    assert result["status"] == "PASS"
    assert result["event_id"] == "evt_test123"
    assert result["critic_score"] == 0.98
    assert result["error"] is None


@pytest.mark.asyncio
async def test_unified_probe_full_failure():
    """Verify probe returns FAIL status and captures errors when endpoints fail."""
    session = MagicMock()
    session.get.side_effect = Exception("Connection Refused")
    session.post.side_effect = Exception("Connection Refused")

    with patch("aiohttp.ClientSession", return_value=AsyncMock(__aenter__=AsyncMock(return_value=session))):
        telemetry = await run_round_table_accountability_probe("http://127.0.0.1:8765")
        assert telemetry["status"] == "FAIL"
        assert telemetry["error"] is not None
        assert "timestamp" in telemetry
