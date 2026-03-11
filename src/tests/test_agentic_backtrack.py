import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logic.cognitive_hub import CognitiveHub

@pytest.mark.asyncio
async def test_agentic_backtrack_logic():
    broadcasted = []
    
    async def mock_broadcast(msg):
        broadcasted.append(msg)

    # Mock Residents
    class MockNode:
        def __init__(self, name):
            self.name = name
            self.call_count = 0
            
        async def call_tool(self, name, params):
            self.call_count += 1
            if self.name == "brain":
                if self.call_count == 1:
                    # Thin response to trigger retry
                    return type('obj', (object,), {'content': [type('obj', (object,), {'text': "Too thin."})()]})
                else:
                    # Dense response to pass fidelity
                    return type('obj', (object,), {'content': [type('obj', (object,), {'text': "This is a much denser technical response about RAPL power and telemetry circuits that should pass the gate."})()]})
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': "Pinky banter narf!"})()]})

    residents = {
        "brain": MockNode("brain"),
        "pinky": MockNode("pinky")
    }

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=mock_broadcast,
        sensory_manager=None,
        brain_online_callback=lambda: True,
        get_oracle_signal_callback=lambda x: "test_signal",
        monitor_task_with_tics_callback=lambda x: x
    )

    # Trigger a strategic query that hits the 'exp_tlm' router
    query = "Analyze the RAPL power logs"
    
    await hub.process_query(query, retry_count=0)
    
    # Brain should have been called twice (initial + 1 retry)
    assert residents["brain"].call_count == 2
    
    # Check if retry message was broadcasted
    retry_msgs = [m for m in broadcasted if "derivation too thin" in str(m.get("brain", ""))]
    assert len(retry_msgs) == 1
    
    # Check final result passed through
    final_msgs = [m for m in broadcasted if "RAPL power and telemetry" in str(m.get("brain", ""))]
    assert len(final_msgs) == 1
