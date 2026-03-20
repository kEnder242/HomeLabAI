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
class FuelMockNode:
    def __init__(self, name, triage_data=None):
        self.name = name
        self.triage_data = triage_data
    
    async def create_message(self, **kwargs):
        async def gen():
            yield f"Result from {self.name}."
        return gen()

    async def call_tool(self, tool, params):
        if tool == "native_sample" and self.triage_data:
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps(self.triage_data)})]})
        return None

async def test_fuel_thresholds():
    print("--- [TEST] Fuel Thresholds & Promotion Logic ---")
    
    scenarios = [
        {
            "name": "BRAIN Forced promotion",
            "triage": {"addressed_to": "BRAIN", "casual": 0.9, "intrigue": 0.1, "importance": 0.1},
            "expected_fuel_min": 0.6,
            "expected_nodes": ["Brain (Intuition)", "Brain (Result)"]
        },
        {
            "name": "PINKY Forced local",
            "triage": {"addressed_to": "PINKY", "casual": 0.1, "intrigue": 0.9, "importance": 0.9},
            "expected_fuel_max": 0.2,
            "expected_nodes": ["Pinky (Triage)"]
        },
        {
            "name": "Natural Overhear (Shadow Only)",
            "triage": {"addressed_to": "MICE", "casual": 0.5, "intrigue": 0.5, "importance": 0.35}, # Fuel = (0.5 * 0.85) / 2 = 0.2125
            "expected_fuel_range": (0.2, 0.6),
            "expected_nodes": ["Pinky (Triage)", "Brain (Intuition)"]
        }
    ]

    for scene in scenarios:
        print(f"\n[SCENARIO] {scene['name']}")
        broadcasts = []
        async def mock_broadcast(msg):
            if "brain_source" in msg:
                broadcasts.append(msg["brain_source"])

        residents = {
            "lab": FuelMockNode("Lab", scene["triage"]),
            "pinky": FuelMockNode("Pinky"),
            "shadow": FuelMockNode("Shadow"),
            "brain": FuelMockNode("Brain")
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

        await hub.process_query("[ME] Scenario Test")
        
        print(f"  Final Fuel: {hub.current_fuel:.2f}")
        print(f"  Nodes Fired: {broadcasts}")

        if "expected_fuel_min" in scene:
            assert hub.current_fuel >= scene["expected_fuel_min"]
        if "expected_fuel_max" in scene:
            assert hub.current_fuel <= scene["expected_fuel_max"]
        
        for node in scene["expected_nodes"]:
            assert node in broadcasts, f"FAILED: {node} did not fire."
        
        print(f"[PASS] {scene['name']} verified.")

    print("\n--- [RESULT] Fuel Logic is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_fuel_thresholds())
