"""[FEAT-518] Unit Test: Double Kickstart Warmup Race Condition Remediation.
Verifies that:
1. bridge_signal_clean returns None when engine yields warming messages.
2. bridge_signal_clean still synthesizes valid non-JSON prose for real user queries.
3. speculative_triage._is_valid_triage rejects any dict containing warming indicators.
"""
import pytest
from logic.cognitive_hub import CognitiveHub
from logic.speculative_triage import SpeculativeTriageRelay

def test_bridge_signal_clean_rejects_warming_notifications():
    hub = CognitiveHub.__new__(CognitiveHub)
    
    warming_texts = [
        "The local engine is warming its anchors right now. Re-connecting momentarily!",
        "Narf! The local engine is warming its anchors... Hold tight, brainiac!",
        "Engine is warming up, please wait.",
        "Error: vLLM connection failed",
        "Connect call failed"
    ]
    
    for text in warming_texts:
        result = hub.bridge_signal_clean(text)
        assert result is None, f"Expected None for warming text: {text}, got: {result}"

def test_bridge_signal_clean_accepts_valid_user_prose():
    hub = CognitiveHub.__new__(CognitiveHub)
    
    user_query = "Hey Pinky, can you inspect the memory allocation on the server?"
    result = hub.bridge_signal_clean(user_query)
    assert result is not None
    assert result.get("addressed_to") == "PINKY"
    assert result.get("importance") == 0.5
    assert result.get("vibe") == "CASUAL"

def test_speculative_triage_rejects_warming_dict():
    relay = SpeculativeTriageRelay(broadcast_callback=None)
    
    fake_warming_result = {
        "vibe": "CASUAL",
        "addressed_to": "PINKY",
        "importance": 0.5,
        "situation": "The local engine is warming its anchors right now."
    }
    assert relay._is_valid_triage(fake_warming_result) is False
    
    valid_result = {
        "vibe": "TECHNICAL",
        "addressed_to": "BRAIN",
        "importance": 0.8,
        "situation": "Investigating GPU thermal throttles"
    }
    assert relay._is_valid_triage(valid_result) is True
