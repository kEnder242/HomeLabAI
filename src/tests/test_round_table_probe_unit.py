"""
[FEAT-608 / FEAT-651 / LAB-110 / BKM-062] Unit Test: Round Table Accountability Probe Verification
Hermetic unit tests for probe_round_table_accountability.py with genuine ledger integration.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from infra.probe_round_table_accountability import (
    extract_judge_score,
    probe_deliberation_circuit,
    probe_greeting_latency,
    run_round_table_accountability_probe,
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
    """Verify deliberation circuit probe succeeds when Foyer inject returns 200 QUEUED and judge score >= 0.70."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "status": "QUEUED",
            "id": "evt_test123",
            "routing": "SYSTEM_HEALTH",
        }
    )
    session.post.return_value.__aenter__.return_value = mock_resp

    with patch("infra.probe_round_table_accountability.extract_judge_score", return_value=(0.98, "High quality consensus")):
        result = await probe_deliberation_circuit(session, "http://127.0.0.1:8765", max_wait_seconds=1.0)
        assert result["status"] == "PASS"
        assert result["event_id"] == "evt_test123"
        assert result["critic_score"] == 0.98
        assert result["error"] is None


@pytest.mark.asyncio
async def test_deliberation_circuit_degraded():
    """Verify probe returns DEGRADED when critic score is below minimum threshold (e.g. 0.45 < 0.70)."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"status": "QUEUED", "id": "evt_low_score"})
    session.post.return_value.__aenter__.return_value = mock_resp

    with patch("infra.probe_round_table_accountability.extract_judge_score", return_value=(0.45, "Shallow answer")):
        result = await probe_deliberation_circuit(session, "http://127.0.0.1:8765", max_wait_seconds=1.0)
        assert result["status"] == "DEGRADED"
        assert result["critic_score"] == 0.45
        assert "Judge score 0.45 < 0.70" in result["error"]


@pytest.mark.asyncio
async def test_deliberation_circuit_timeout_fail_fast():
    """Verify deliberation fails fast with clear diagnostic message if triage never completes."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"status": "QUEUED", "id": "evt_timed_out"})
    session.post.return_value.__aenter__.return_value = mock_resp

    with patch("infra.probe_round_table_accountability.extract_judge_score", return_value=(0.0, "No score")):
        result = await probe_deliberation_circuit(session, "http://127.0.0.1:8765", max_wait_seconds=0.1)
        assert result["status"] == "FAIL"
        assert "did not complete within" in result["error"]


@pytest.mark.asyncio
async def test_unified_probe_full_failure():
    """Verify probe returns FAIL status and captures errors when endpoints fail."""
    session = MagicMock()
    session.get.side_effect = Exception("Connection Refused")
    session.post.side_effect = Exception("Connection Refused")

    with patch(
        "aiohttp.ClientSession",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=session)),
    ):
        telemetry = await run_round_table_accountability_probe("http://127.0.0.1:8765")
        assert telemetry["status"] == "FAIL"
        assert telemetry["error"] is not None
        assert "timestamp" in telemetry
