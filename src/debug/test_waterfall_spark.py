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
    def __init__(self, name):
        self.name = name
    async def create_message(self, **kwargs):
        async def mock_generator():
            tokens = [f"[{self.name}] ", "Token 1, ", "Token 2, ", "Final."]
            for t in tokens:
                await asyncio.sleep(0.1) # Simulate network/inference latency
                yield t
        return mock_generator()
    
    async def call_tool(self, tool, params):
        if tool == "native_sample":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': '{"intent": "STRATEGIC", "importance": 0.8, "casual": 0.1, "intrigue": 0.9, "topic": "Testing"} '})]})
        return None

async def test_waterfall_spark():
    print("--- [TEST] Waterfall Spark & Handshake Tic ---")
    
    broadcasts = []
    async def mock_broadcast(msg):
        broadcasts.append(msg)
        if msg.get("type") == "crosstalk":
            print(f"  [WS] Crosstalk: {msg.get('brain')}")
        else:
            print(f"  [WS] Dispatch: {msg.get('brain')} ({msg.get('brain_source')})")

    residents = {
        "lab": MockNode("Lab"),
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
    hub.is_extraction = True # Disable audit for mock test

    print("[STEP 1] Processing High-Fuel Query...")
    start_time = asyncio.get_event_loop().time()
    await hub.process_query("Test high fuel waterfall", trigger_briefing_callback=None)
    end_time = asyncio.get_event_loop().time()
    
    total_duration = end_time - start_time
    print(f"[STEP 2] Turn Complete in {total_duration:.2f}s")

    # Verify Handshake Tics
    tics = [b for b in broadcasts if b.get("type") == "crosstalk"]
    assert len(tics) >= 3, f"Expected at least 3 handshake tics, got {len(tics)}"
    print("[PASS] Handshake Tics verified.")

    # Verify Sequential Pop (Paragraph Pop)
    dispatches = [b for b in broadcasts if b.get("brain_source") in ["Pinky (Triage)", "Brain (Intuition)", "Brain (Result)"]]
    assert len(dispatches) == 3
    print("[PASS] Paragraph Pop buffering verified.")

    print("--- [RESULT] Waterfall Logic is RESONANT ---")

if __name__ == "__main__":
    asyncio.run(test_waterfall_spark())
