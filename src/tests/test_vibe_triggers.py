import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, ANY
from src.logic.cognitive_hub import CognitiveHub

@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    pinky.list_tools = AsyncMock()
    pinky.list_tools.return_value = MagicMock(tools=[MagicMock(name="facilitate")])
    
    brain = MagicMock()
    brain.call_tool = AsyncMock()
    brain.list_tools = AsyncMock()
    brain.list_tools.return_value = MagicMock(tools=[MagicMock(name="deep_think")])
    
    return {"pinky": pinky, "brain": brain}

@pytest.fixture
def hub(mock_residents):
    broadcast = AsyncMock()
    sensory = MagicMock()
    brain_online = MagicMock(return_value=True)
    get_oracle = MagicMock(return_value="Oracle Signal")
    
    async def monitor_pass_through(coro):
        return await coro
    monitor = AsyncMock(side_effect=monitor_pass_through)
    
    return CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        brain_online_callback=brain_online,
        get_oracle_signal_callback=get_oracle,
        monitor_task_with_tics_callback=monitor
    )

@pytest.mark.asyncio
async def test_vibe_casual_greeting(hub):
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    await hub.process_query("Hi there!")
    # Verified as casual greeting (Pinky)
    hub.residents["pinky"].call_tool.assert_called_with("facilitate", ANY)
    # Check that Brain was NOT called for deep_think
    assert not hub.residents["brain"].call_tool.called

@pytest.mark.asyncio
async def test_vibe_narf(hub):
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    await hub.process_query("Narf!")
    hub.residents["pinky"].call_tool.assert_called_with("facilitate", ANY)
    assert not hub.residents["brain"].call_tool.called

@pytest.mark.asyncio
async def test_vibe_strategic_technical(hub):
    # This should go to Brain
    hub.execute_dispatch = AsyncMock(return_value=True)
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Analyzing thermal profile.")])
    hub.residents["brain"].call_tool.return_value = MagicMock(content=[MagicMock(text="The 2080 Ti has a high thermal density due to the TU102 core.")])
    
    await hub.process_query("What is the thermal profile of the 2080 Ti?")
    
    # Verify Brain was called
    assert hub.residents["brain"].call_tool.called
    # Verify Pinky interjected
    assert any("STRATEGIC_INTENT" in str(c) for c in hub.residents["pinky"].call_tool.call_args_list)

@pytest.mark.asyncio
async def test_vibe_morning_briefing_trigger(hub):
    # "Any updates?" -> Morning Briefing tool trigger.
    # Assume Pinky handles this casual-looking but functional query
    tool_call = json.dumps({"tool": "trigger_morning_briefing"})
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text=tool_call)])
    
    trigger_callback = AsyncMock()
    
    # We do NOT mock execute_dispatch here to allow the internal callback to be triggered
    # But we need to make sure broadcast doesn't fail
    hub.broadcast = AsyncMock()

    await hub.process_query("Any updates?", trigger_briefing_callback=trigger_callback)
    
    # Verify trigger_callback was called
    assert trigger_callback.called
