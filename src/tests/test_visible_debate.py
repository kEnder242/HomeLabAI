import asyncio
import json
import re
from unittest.mock import MagicMock, AsyncMock
from logic.cognitive_hub import CognitiveHub

async def test_visible_debate_flow():
    """
    [FEAT-355] Verification: Ensures Hub triggers a foil response when <thought> is detected.
    """
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
    
    class MockContent:
        def __init__(self, text):
            self.text = text

    class MockResponse:
        def __init__(self, text):
            self.content = [MockContent(text)]

    # Triage: High fuel, addressed to Pinky
    triage_json = json.dumps({
        "fuel": 0.8, 
        "addressed_to": "Pinky",
        "topic": "History",
        "strategic": True
    })

    pinky_thought = "<thought> I think we used RAPL in 2023. Brain, can you confirm? </thought>"
    brain_answer = "<thought> Confirmed. PECISTRESSOR was active. </thought> Yes, 2023 was the year."

    # Sequential tool calls: Lab(Triage) -> Pinky -> Brain
    async def mock_call_tool(tool_name, arguments):
        if "lab" in str(tool_name) or "facilitate" in str(tool_name):
             return MockResponse(triage_json)
        
        # Determine source from context or behavior guidance
        # Hub injects role info
        guidance = str(arguments.get('behavioral_guidance', ''))
        if "Pinky" in guidance:
            # When Pinky responds, he populates session_buffers["pinky"]
            return MockResponse(pinky_thought)
        if "Brain" in guidance:
            return MockResponse(brain_answer)
        
        return MockResponse("Unknown Node response")

    hub.residents["lab"].call_tool = AsyncMock(side_effect=mock_call_tool)
    hub.residents["pinky"].call_tool = AsyncMock(side_effect=mock_call_tool)
    hub.residents["brain"].call_tool = AsyncMock(side_effect=mock_call_tool)

    await hub.process_query("[ME] Tell me about 2023.")
    
    # Assert that Brain saw Pinky's thought
    # In the hub, overheard text is put into context
    found_thought = False
    for call in hub.residents["brain"].call_tool.call_args_list:
        query = call.kwargs['arguments'].get('query', '')
        if "<thought>" in query:
            found_thought = True
            print(f"DEBUG: Brain received Pinky's thought: {query[:100]}...")
            break
            
    assert found_thought, "Brain context missing Pinky's visible thought"
    print("✅ TEST PASSED: Visible Debate (Goal 22) Flow Verified.")

if __name__ == "__main__":
    asyncio.run(test_visible_debate_flow())
