import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from logic.speculative_triage import (
    _load_engine_seats,
    _probe_seat,
    resolve_active_deep_thought_target,
    SpeculativeTriageRelay
)

def test_load_engine_seats():
    """Verify declarative engine seats load correctly from infrastructure.json."""
    seats = _load_engine_seats()
    assert isinstance(seats, list)
    assert len(seats) >= 3
    seat_ids = [s["id"] for s in seats]
    assert "M5_AIR" in seat_ids
    assert "KENDER" in seat_ids
    assert "LOCAL" in seat_ids

def test_resolve_active_seat_fallback_to_local():
    """Verify fallback to LOCAL when remote seats fail probe."""
    mock_seats = [
        {"id": "M5_AIR", "name": "M5_AIR", "host": "192.0.2.1", "port": 8000, "t_warmed": 0.09, "t_cold": 0.85},
        {"id": "KENDER", "name": "KENDER", "host": "192.0.2.2", "port": 11434, "t_warmed": 0.12, "t_cold": 1.2},
        {"id": "LOCAL", "name": "LOCAL", "host": "127.0.0.1", "port": 8088, "t_warmed": 0.045, "t_cold": 0.05}
    ]
    with patch("logic.speculative_triage._probe_seat", return_value=False):
        target = resolve_active_deep_thought_target(mock_seats)
        assert target["id"] == "LOCAL"

def test_resolve_active_seat_m5_air_priority():
    """Verify M5_AIR is chosen when responsive."""
    mock_seats = [
        {"id": "M5_AIR", "name": "M5_AIR", "host": "192.168.1.46", "port": 8000, "t_warmed": 0.09, "t_cold": 0.85},
        {"id": "KENDER", "name": "KENDER", "host": "192.168.1.26", "port": 11434, "t_warmed": 0.12, "t_cold": 1.2},
        {"id": "LOCAL", "name": "LOCAL", "host": "127.0.0.1", "port": 8088, "t_warmed": 0.045, "t_cold": 0.05}
    ]
    def mock_probe(seat):
        return seat["id"] == "M5_AIR"

    with patch("logic.speculative_triage._probe_seat", side_effect=mock_probe):
        target = resolve_active_deep_thought_target(mock_seats)
        assert target["id"] == "M5_AIR"
        assert target["t_warmed"] == 0.09

@pytest.mark.asyncio
async def test_speculative_relay_2x_headstart_window():
    """Verify speculative relay sets head_start_window to 2 * t_warmed."""
    broadcast_mock = AsyncMock()
    vllm_mock = AsyncMock(return_value={"vibe": "CASUAL", "addressed_to": "PINKY", "importance": 0.1})
    relay = SpeculativeTriageRelay(broadcast_mock, vllm_fn=vllm_mock, t_warmed=0.09)
    assert relay.head_start_window == pytest.approx(0.18, rel=1e-2)
