import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock
from logic.cognitive_hub import CognitiveHub

async def test_persistent_foil_memory():
    """
    [FEAT-356] Verification: Ensures Turn-1 corrections are visible in Turn-2.
    """
    # Setup Hub with Mock Residents
    residents = {
        "pinky": MagicMock(),
        "shadow": MagicMock(),
        "brain": MagicMock(),
        "lab": MagicMock()
    }
    
    # Mock Constructor Args
    broadcast = AsyncMock()
    sensory = MagicMock()
    get_vram = MagicMock()
    briefing = AsyncMock()
    tics = AsyncMock()
    
    hub = CognitiveHub(residents, broadcast, sensory, get_vram, briefing, tics)
    
    # Turn 1: Brain corrects Pinky
    turn_1_dialogue = "Pinky: Narf! RAPL is on port 8080. Brain: Negative. RAPL is on 9100."
    hub.round_table_memory.append(turn_1_dialogue)
    
    # Mock Response Class
    class MockContent:
        def __init__(self, text):
            self.text = text

    class MockResponse:
        def __init__(self, text):
            self.content = [MockContent(text)]

    triage_json = json.dumps({
        "fuel": 0.1,
        "topic": "Casual",
        "addressed_to": "Pinky",
        "strategic": False
    })

    # Mock Triage
    hub.residents["lab"].call_tool = AsyncMock(return_value=MockResponse(triage_json))
    # Mock Pinky
    hub.residents["pinky"].call_tool = AsyncMock(return_value=MockResponse("Narf! I remember now."))
    
    await hub.process_query("[ME] What port was RAPL on again?")
    
    # Verify Pinky call arguments
    found_context = False
    for call in hub.residents["pinky"].call_tool.call_args_list:
        if 'arguments' in call.kwargs:
            query = call.kwargs['arguments'].get('query', '')
            if "[PREVIOUS_DEBATE]" in query and "9100" in query:
                found_context = True
                print(f"DEBUG: Found injected context in call to Pinky: {query[:100]}...")
                break
    
    assert found_context, "Context missing Turn-1 memory injection"
    print("✅ TEST PASSED: Foil-Aware Memory (Goal 23) Verified.")

if __name__ == "__main__":
    asyncio.run(test_persistent_foil_memory())
