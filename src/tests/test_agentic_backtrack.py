import pytest
import os
import sys
import json
from unittest.mock import patch, AsyncMock, MagicMock

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
            
        async def list_tools(self):
            return MagicMock(tools=[MagicMock(name="reply_to_user")])

        async def call_tool(self, name, params):
            self.call_count += 1
            if self.name == "brain":
                if self.call_count == 1:
                    # Thin response to trigger retry
                    return type('obj', (object,), {'content': [type('obj', (object,), {'text': "Too thin."})()]})
                else:
                    # Dense response to pass fidelity (Retry 1 or 2)
                    return type('obj', (object,), {'content': [type('obj', (object,), {'text': "This is a much denser technical response about RAPL power and telemetry circuits that should pass the gate."})()]})
            
            # Pinky response: Just natural language for triage pass
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': "I sense technical depth. Let's ask the Brain."})()]})

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
    
    # Brain should have been called 3 times:
    # 1. Initial Call (Thin -> Trigger Pivot)
    # 2. Pivot Call (Retry 1) (Thin -> Trigger Hallway)
    # 3. Hallway Call (Retry 2) (Dense -> Finish)
    assert residents["brain"].call_count == 3
    
    # Check if retry message was broadcasted
    retry_msgs = [m for m in broadcasted if "derivation too thin" in str(m.get("brain", ""))]
    assert len(retry_msgs) >= 1

@pytest.mark.asyncio
async def test_hallway_protocol_trigger():
    broadcasted = []
    
    async def mock_broadcast(msg):
        broadcasted.append(msg)

    # Mock Residents
    class MockNode:
        def __init__(self, name):
            self.name = name
            self.call_count = 0
            
        async def list_tools(self):
            return MagicMock(tools=[MagicMock(name="reply_to_user")])

        async def call_tool(self, name, params):
            self.call_count += 1
            if self.name == "brain":
                # Always return thin response to force all retries
                return type('obj', (object,), {'content': [type('obj', (object,), {'text': "Still too thin."})()]})
            
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': "Searching deep..."})()]})

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

    with patch('asyncio.create_subprocess_exec') as mock_sub:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"output", b"error")
        mock_proc.returncode = 0
        mock_sub.return_value = mock_proc
        
        query = "Analyze the RAPL power logs"
        # Force start at retry_count 1 to hit the hallway check
        await hub.process_query(query, retry_count=1)
        
        # Should have triggered hallway protocol message
        hallway_msgs = [m for m in broadcasted if "performing deep archival harvest" in str(m.get("brain", ""))]
        assert len(hallway_msgs) >= 1
        
        # Should have called subprocess
        assert mock_sub.called
        args, kwargs = mock_sub.call_args
        assert "mass_scan.py" in args[1]
        assert "--keyword" in args
