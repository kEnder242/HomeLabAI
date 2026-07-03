import pytest
import json
from unittest.mock import AsyncMock, MagicMock, ANY
from src.logic.cognitive_hub import CognitiveHub

@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    pinky.list_tools = AsyncMock()
    pinky.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])
    
    brain = MagicMock()
    brain.call_tool = AsyncMock()
    brain.list_tools = AsyncMock()
    brain.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])
    
    lab = MagicMock()
    lab.call_tool = AsyncMock()
    lab.list_tools = MagicMock()
    
    thought = MagicMock()
    thought.call_tool = AsyncMock()
    thought.list_tools = MagicMock()
    
    return {"pinky": pinky, "brain": brain, "lab": lab, "thought": thought}

@pytest.fixture
def hub(mock_residents):
    broadcast = AsyncMock()
    sensory = MagicMock()
    
    return CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=lambda: True,
        trigger_morning_briefing=AsyncMock(),
        set_active_domain=MagicMock()
    )

@pytest.mark.asyncio
async def test_vibe_casual_greeting(hub):
    # Set up triage response for casual query
    triage_call = json.dumps({"addressed_to": "PINKY", "vibe": "CASUAL", "domain": "standard", "casual": 0.9, "intrigue": 0.1, "importance": 0.1})
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=triage_call)])
    
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Hello, Jason! Narf!")])
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    await hub.process_query("Hi there!")
    # Verified as casual greeting (Pinky think tool)
    hub.residents["pinky"].call_tool.assert_called_with("think", ANY)
    # Check that Brain was NOT called
    assert not hub.residents["brain"].call_tool.called

@pytest.mark.asyncio
async def test_vibe_narf(hub):
    triage_call = json.dumps({"addressed_to": "PINKY", "vibe": "CASUAL", "domain": "standard", "casual": 0.9, "intrigue": 0.1, "importance": 0.1})
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=triage_call)])
    
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Narf! I'm ready!")])
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    await hub.process_query("Narf!")
    hub.residents["pinky"].call_tool.assert_called_with("think", ANY)
    assert not hub.residents["brain"].call_tool.called

@pytest.mark.asyncio
async def test_vibe_strategic_technical(hub):
    # This should go to Brain/Deep Thought
    triage_call = json.dumps({"addressed_to": "BRAIN", "vibe": "TECHNICAL", "domain": "exp_tlm", "casual": 0.0, "intrigue": 0.8, "importance": 0.8})
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=triage_call)])
    
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Analyzing thermal profile.")])
    hub.residents["thought"].call_tool.return_value = MagicMock(content=[MagicMock(text="The 2080 Ti has a high thermal density due to the TU102 core.")])
    
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    await hub.process_query("What is the thermal profile of the 2080 Ti?")
    
    # Verify thought node was called for the deep leg
    assert hub.residents["thought"].call_tool.called

@pytest.mark.asyncio
async def test_vibe_morning_briefing_trigger(hub):
    # "Any updates?" -> Morning Briefing tool trigger.
    # Set up triage to route to Pinky
    triage_call = json.dumps({"addressed_to": "PINKY", "vibe": "CASUAL", "domain": "standard", "casual": 0.8, "intrigue": 0.2, "importance": 0.2})
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=triage_call)])
    
    # Pinky output matches the morning briefing tool trigger JSON
    tool_call = json.dumps({"tool": "trigger_morning_briefing"})
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text=tool_call)])
    
    trigger_callback = AsyncMock()
    hub.broadcast = AsyncMock()

    await hub.process_query("Any updates?", trigger_briefing_callback=trigger_callback)
    
    # Verify trigger_callback was called because the tool call was intercepted
    assert trigger_callback.called


@pytest.mark.asyncio
async def test_vibe_triage_driven_morning_briefing_trigger(hub):
    # Set up triage to return situation=morning_briefing / hints=trigger_morning_briefing
    triage_call = json.dumps({
        "addressed_to": "PINKY",
        "vibe": "CASUAL",
        "domain": "standard",
        "casual": 0.9,
        "intrigue": 0.1,
        "importance": 0.1,
        "situation": "morning_briefing",
        "hints": "trigger_morning_briefing"
    })
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=triage_call)])
    
    trigger_callback = AsyncMock()
    hub.broadcast = AsyncMock()

    await hub.process_query("What's up?", trigger_briefing_callback=trigger_callback)
    
    # Verify trigger_callback was called directly from the triage gate
    assert trigger_callback.called

