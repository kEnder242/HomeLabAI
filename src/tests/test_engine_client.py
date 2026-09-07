import pytest
import unittest
from unittest.mock import patch, MagicMock
import json
import socket

from infra.engine_client import (
    load_engine_seats,
    probe_tcp,
    probe_seat,
    resolve_active_deep_thought_target,
    query_sovereign_engine
)
from forge.distill_gems import distill_gem

def test_load_engine_seats_returns_valid_ladder():
    """Verify engine seats are loaded with M5_AIR, KENDER, and LOCAL fallback."""
    seats = load_engine_seats()
    assert isinstance(seats, list)
    assert len(seats) >= 3
    seat_ids = [s["id"] for s in seats]
    assert "M5_AIR" in seat_ids
    assert "KENDER" in seat_ids
    assert "LOCAL" in seat_ids

def test_probe_tcp_closed_port_fails_sub_200ms():
    """Verify probe_tcp cleanly returns False for an unused port within 200ms."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        unused_port = s.getsockname()[1]
    # Port is closed immediately after context manager exits
    assert probe_tcp("127.0.0.1", unused_port, timeout=0.2) is False

def test_resolve_active_target_cascades_to_local_when_remotes_offline():
    """Verify resolution automatically cascades to LOCAL when M5 and KENDER are offline."""
    simulated_seats = [
        {"id": "M5_AIR", "host": "192.0.2.1", "port": 8000, "protocol": "OPENAI", "t_cold": 0.1},
        {"id": "KENDER", "host": "192.0.2.2", "port": 11434, "protocol": "OLLAMA", "t_cold": 0.1},
        {"id": "LOCAL", "host": "127.0.0.1", "port": 8088, "protocol": "OPENAI", "default_model": "shadow_brain_v2"}
    ]
    with patch("infra.engine_client.probe_seat", return_value=False):
        target = resolve_active_deep_thought_target(simulated_seats)
        assert target["id"] == "LOCAL"
        assert target["host"] == "127.0.0.1"

def test_query_sovereign_engine_openai_protocol_mock():
    """Verify query_sovereign_engine formats and parses OpenAI JSON responses."""
    simulated_seats = [
        {"id": "M5_AIR", "host": "192.168.1.46", "port": 8000, "protocol": "OPENAI", "default_model": "mlx-qwen"}
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({"instruction": "What is RAPL?", "response": "Running Average Power Limit."})
            }
        }]
    }

    with patch("infra.engine_client.probe_seat", return_value=True):
        with patch("requests.post", return_value=mock_resp) as mock_post:
            res = query_sovereign_engine("Extract GEM", json_mode=True, seats=simulated_seats)
            assert isinstance(res, dict)
            assert res["instruction"] == "What is RAPL?"
            assert res["response"] == "Running Average Power Limit."
            assert mock_post.called
            assert mock_post.call_args[0][0] == "http://192.168.1.46:8000/v1/chat/completions"

def test_query_sovereign_engine_ollama_fallback_mock():
    """Verify query_sovereign_engine falls back to Kender/Ollama if M5 Air fails."""
    simulated_seats = [
        {"id": "M5_AIR", "host": "192.168.1.46", "port": 8000, "protocol": "OPENAI", "default_model": "mlx-qwen"},
        {"id": "KENDER", "host": "192.168.1.26", "port": 11434, "protocol": "OLLAMA", "default_model": "qwen3:14b"},
        {"id": "LOCAL", "host": "127.0.0.1", "port": 8088, "protocol": "OPENAI", "default_model": "shadow_brain_v2"}
    ]
    # M5 Air returns 500, KENDER returns 200
    m5_resp = MagicMock()
    m5_resp.status_code = 500

    kender_resp = MagicMock()
    kender_resp.status_code = 200
    kender_resp.json.return_value = {
        "message": {
            "content": json.dumps({"instruction": "What is PECI?", "response": "Platform Environment Control Interface."})
        }
    }

    def post_side_effect(url, **kwargs):
        if "192.168.1.46" in url:
            return m5_resp
        elif "192.168.1.26" in url:
            return kender_resp
        return MagicMock(status_code=500)

    with patch("infra.engine_client.probe_seat", return_value=True):
        with patch("requests.post", side_effect=post_side_effect):
            res = query_sovereign_engine("Extract GEM", json_mode=True, seats=simulated_seats)
            assert isinstance(res, dict)
            assert res["instruction"] == "What is PECI?"

def test_distill_gem_integration():
    """Verify distill_gem outputs valid training pair dictionary via query_sovereign_engine."""
    test_gem = {
        "summary": "PECI Thermal Throttling Calibration",
        "rank": 4,
        "detail": "MSR 0x1B0 telemetry confirmed 15W drop."
    }
    mock_pair = {
        "instruction": "How do you calibrate PECI thermal throttling?",
        "response": "Inspect MSR 0x1B0 telemetry and monitor package power baseline."
    }
    with patch("forge.distill_gems.query_sovereign_engine", return_value=mock_pair):
        result = distill_gem(test_gem)
        assert result is not None
        assert result["instruction"] == mock_pair["instruction"]
        assert result["response"] == mock_pair["response"]
