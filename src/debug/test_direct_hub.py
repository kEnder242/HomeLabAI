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

# Mock Node that mimics real behavior but stays local
class RealishMockNode:
    def __init__(self, name, triage_data=None):
        self.name = name
        self.triage_data = triage_data
    
    async def create_message(self, **kwargs):
        async def gen():
            yield f"High-fidelity response from {self.name}. "
            yield "Verified logic standing by."
        return gen()

    async def call_tool(self, tool, params):
        if tool == "native_sample" and self.triage_data:
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps(self.triage_data)})]})
        return None

async def test_direct_hub_steerage():
    print("--- [TEST] Direct Hub Steerage (No WebSockets) ---")
    
    broadcasts = []
    async def mock_broadcast(msg):
        broadcasts.append(msg)
        if "brain_source" in msg:
            print(f"  [HUB -> UI] {msg['brain_source']}: {msg['brain'][:50]}...")

    # Scenario: Direct Address Brain
    triage = {
        "intent": "STRATEGIC",
        "addressed_to": "BRAIN",
        "vibe": "BRAIN_STRATEGY",
        "importance": 0.8,
        "casual": 0.1,
        "intrigue": 0.9
    }

    residents = {
        "lab": RealishMockNode("Lab", triage),
        "pinky": RealishMockNode("Pinky"),
        "shadow": RealishMockNode("Shadow"),
        "brain": RealishMockNode("Brain")
    }

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=mock_broadcast,
        sensory_manager=None,
        brain_online_callback=True,
        get_oracle_signal_callback=lambda x: "Oracle Signal",
        monitor_task_with_tics_callback=None
    )
    hub.is_extraction = True

    print("\n[STEP 1] Testing 'addressed_to: BRAIN'...")
    await hub.process_query("[ME] Hi Brain, check the logs.")
    
    sources = [b.get("brain_source") for b in broadcasts if "brain_source" in b]
    print(f"  Captured Sources: {sources}")
    
    assert "Brain (Intuition)" in sources
    assert "Pinky (Triage)" not in sources, "FAILED: Pinky should have been MUTED for direct Brain address."
    print("[PASS] Speaker Masking (Pinky Muted) verified.")

    # Scenario: Direct Address Pinky
    broadcasts.clear()
    hub.residents["lab"].triage_data["addressed_to"] = "PINKY"
    hub.residents["lab"].triage_data["vibe"] = "PINKY_INTERFACE"
    hub.residents["lab"].triage_data["importance"] = 0.2
    
    print("\n[STEP 2] Testing 'addressed_to: PINKY'...")
    await hub.process_query("[ME] Pinky, tell me a joke.")
    
    sources = [b.get("brain_source") for b in broadcasts if "brain_source" in b]
    print(f"  Captured Sources: {sources}")
    
    assert "Pinky (Triage)" in sources
    assert "Brain (Intuition)" not in sources, "FAILED: Shadow should have been MUTED for direct Pinky address."
    print("[PASS] Speaker Masking (Shadow Muted) verified.")

    print("\n--- [RESULT] Hub Steerage is NOMINAL ---")

if __name__ == "__main__":
    asyncio.run(test_direct_hub_steerage())
