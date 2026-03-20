import asyncio
import json
import logging
import sys
import os

# Paths
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_SELF_DIR)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from logic.cognitive_hub import CognitiveHub

# Mock Objects
class MockNode:
    def __init__(self, name, triage_json=None):
        self.name = name
        self.triage_json = triage_json
    
    async def create_message(self, **kwargs):
        async def mock_generator():
            yield f"Response from {self.name}."
        return mock_generator()
    
    async def call_tool(self, tool, params):
        if tool == "native_sample" and self.triage_json:
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': self.triage_json})]})
        return None

async def test_speaker_masking():
    print("--- [TEST] Speaker Masking & Direct Address ---")
    
    scenarios = [
        {
            "name": "Direct Address: BRAIN",
            "query": "Hi Brain!",
            "triage": '{"intent": "STRATEGIC", "addressed_to": "BRAIN", "vibe": "BRAIN_STRATEGY", "importance": 0.5, "casual": 0.5, "intrigue": 0.5}',
            "expected_sources": ["Brain (Intuition)"], # Pinky should be MUTED
            "unexpected_sources": ["Pinky (Triage)"]
        },
        {
            "name": "Direct Address: PINKY",
            "query": "Hey Pinky, what's up?",
            "triage": '{"intent": "CASUAL", "addressed_to": "PINKY", "vibe": "PINKY_INTERFACE", "importance": 0.1, "casual": 0.9, "intrigue": 0.1}',
            "expected_sources": ["Pinky (Triage)"], # Brain/Shadow should be MUTED
            "unexpected_sources": ["Brain (Intuition)", "Brain (Result)"]
        },
        {
            "name": "Collective Address: MICE",
            "query": "Hi mice, status report!",
            "triage": '{"intent": "STRATEGIC", "addressed_to": "MICE", "vibe": "MICE_COLLABORATION", "importance": 0.6, "casual": 0.2, "intrigue": 0.6}',
            "expected_sources": ["Pinky (Triage)", "Brain (Intuition)"], # Everyone speaks
            "unexpected_sources": []
        }
    ]

    for scene in scenarios:
        print(f"\n[SCENARIO] {scene['name']}")
        broadcasts = []
        async def mock_broadcast(msg):
            if "brain_source" in msg:
                broadcasts.append(msg["brain_source"])
                print(f"  [WS] Source: {msg['brain_source']}")

        residents = {
            "lab": MockNode("Lab", triage_json=scene["triage"]),
            "pinky": MockNode("Pinky"),
            "shadow": MockNode("Shadow"),
            "brain": MockNode("Brain")
        }

        hub = CognitiveHub(
            residents=residents,
            broadcast_callback=mock_broadcast,
            sensory_manager=None,
            brain_online_callback=True,
            get_oracle_signal_callback=lambda x: "Oracle Signal",
            monitor_task_with_tics_callback=None
        )
        hub.is_extraction = True # Disable audit

        await hub.process_query(scene["query"])
        
        # Validation
        for expected in scene["expected_sources"]:
            assert expected in broadcasts, f"FAILED: {expected} should have spoken in {scene['name']}"
        
        for unexpected in scene["unexpected_sources"]:
            assert unexpected not in broadcasts, f"FAILED: {unexpected} should have been MUTED in {scene['name']}"
            
        print(f"[PASS] {scene['name']} verified.")

    print("\n--- [RESULT] Speaker Masking is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_speaker_masking())
