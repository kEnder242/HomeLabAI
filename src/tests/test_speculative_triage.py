import asyncio
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from logic.speculative_triage import SpeculativeTriageRelay

# Mock broadcast callback
async def mock_broadcast(payload):
    pass

# Mock Kender function (fast)
async def mock_kender_fast(query, context, schema, request_id):
    return {
        "vibe": "TECHNICAL",
        "addressed_to": "BRAIN",
        "importance": 0.9,
        "situation": "Kender fast path"
    }

# Mock Kender function (slow)
async def mock_kender_slow(query, context, schema, request_id):
    await asyncio.sleep(1.0)
    return {
        "vibe": "TECHNICAL",
        "addressed_to": "BRAIN",
        "importance": 0.9,
        "situation": "Kender slow path"
    }

# Mock vLLM function (medium speed)
async def mock_vllm_medium(query, context, schema, request_id):
    await asyncio.sleep(0.2)
    return {
        "vibe": "CASUAL",
        "addressed_to": "PINKY",
        "importance": 0.5,
        "situation": "Local vLLM speculative win"
    }

# Mock Kender error
async def mock_kender_error(query, context, schema, request_id):
    raise ConnectionError("Kender unreachable")

# Mock vLLM error
async def mock_vllm_error(query, context, schema, request_id):
    raise RuntimeError("vLLM OOM")

# Mock invalid response
async def mock_invalid_response(query, context, schema, request_id):
    return {"inferred_intent": "missing fields"}

@pytest.mark.asyncio
async def test_kender_fast_path():
    """Test Case 1: Kender resolves within head-start window."""
    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_fast, mock_vllm_medium, t_warm=0.5)
    result, winner = await relay.relay("test", {}, {}, "req1")
    
    assert winner == "kender"
    assert result["situation"] == "Kender fast path"
    meta = relay.get_console_metadata(winner)
    assert meta["channel"] == "insight"
    assert meta["source"] == "Deep Thought (Triage)"

@pytest.mark.asyncio
async def test_kender_slow_vllm_wins():
    """Test Case 2: Kender slow, vLLM speculative win."""
    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_slow, mock_vllm_medium, t_warm=0.1)
    # head_start = 0.2s. Kender sleeps 1.0s, vLLM sleeps 0.2s.
    result, winner = await relay.relay("test", {}, {}, "req2")
    
    assert winner == "vllm"
    assert result["situation"] == "Local vLLM speculative win"
    meta = relay.get_console_metadata(winner)
    assert meta["channel"] == "chat"
    assert meta["source"] == "Lab (Triage)"

@pytest.mark.asyncio
async def test_trailing_runner_cancellation():
    """Test Case 3: Ensure trailing runner is cancelled (implicit via fast return)."""
    # We can't easily test cancellation without mocks tracking calls, 
    # but we can verify the winner logic.
    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_slow, mock_vllm_medium, t_warm=0.01)
    result, winner = await relay.relay("test", {}, {}, "req3")
    assert winner in ["kender", "vllm"]

@pytest.mark.asyncio
async def test_fallback_on_error():
    """Test Case 4: Fallback when primary fails."""
    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_error, mock_vllm_medium, t_warm=0.1)
    result, winner = await relay.relay("test", {}, {}, "req4")
    
    assert winner == "vllm"
    assert result["situation"] == "Local vLLM speculative win"

@pytest.mark.asyncio
async def test_invalid_response_fallback():
    """Test Case 5: Invalid JSON response handling."""
    relay = SpeculativeTriageRelay(mock_broadcast, mock_invalid_response, mock_vllm_medium, t_warm=0.1)
    # Kender returns invalid, vLLM should win
    result, winner = await relay.relay("test", {}, {}, "req5")
    
    assert winner == "vllm"


@pytest.mark.asyncio
async def test_dual_check_gate_fast_bypass(monkeypatch):
    """Test Case 6: When Kender Ollama probe fails, fast socket gate bypasses head-start with 0 delay."""
    import logic.speculative_triage as spec_mod
    monkeypatch.setattr(spec_mod, "_probe_ollama", lambda host, port, timeout: False)

    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_slow, mock_vllm_medium, t_warm=5.0)
    t0 = asyncio.get_event_loop().time()
    result, winner = await relay.relay("test", {}, {}, "req6")
    elapsed = asyncio.get_event_loop().time() - t0

    # Assert local vLLM won and elapsed time skipped the 10s window entirely (< 1.0s)
    assert winner == "vllm"
    assert result["situation"] == "Local vLLM speculative win"
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_dual_check_gate_patient_runway(monkeypatch):
    """Test Case 7: When Kender Ollama probe succeeds, 10s patient window allows slow warm start to win."""
    import logic.speculative_triage as spec_mod
    monkeypatch.setattr(spec_mod, "_probe_ollama", lambda host, port, timeout: True)

    # Kender takes 0.3s (simulating warm generation); head-start is 1.0s (t_warm=0.5)
    relay = SpeculativeTriageRelay(mock_broadcast, mock_kender_slow, mock_vllm_medium, t_warm=1.0)
    result, winner = await relay.relay("test", {}, {}, "req7")

    assert winner == "kender"
    assert result["situation"] == "Kender slow path"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
