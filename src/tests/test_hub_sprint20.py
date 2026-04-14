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
    
    shadow = MagicMock()
    shadow.call_tool = AsyncMock()
    shadow.list_tools = AsyncMock()
    shadow.list_tools.return_value = MagicMock(tools=[MagicMock(name="ask_brain")])
    
    # [SPR-20] Add lab node for triage
    lab = MagicMock()
    lab.call_tool = AsyncMock()
    
    return {"pinky": pinky, "brain": brain, "shadow": shadow, "lab": lab}

@pytest.fixture
def hub(mock_residents):
    broadcast = AsyncMock()
    sensory = MagicMock()
    # [SPR-20] Updated callback name
    get_vram_status = MagicMock(return_value=True)
    trigger_morning = AsyncMock()
    
    async def monitor_pass_through(coro):
        return await coro
    monitor = AsyncMock(side_effect=monitor_pass_through)
    
    hub_inst = CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=get_vram_status, # [SPR-20] Fixed constructor
        trigger_morning_briefing=trigger_morning,
        monitor_task_with_tics=monitor
    )
    # Mock some basic anchors if file not found
    hub_inst.intent_anchors = {
        "telemetry": {"adapter": "exp_tlm", "anchors": ["telemetry", "thermal", "rapl"]},
        "architecture": {"adapter": "exp_bkm", "anchors": ["architecture", "bkm"]},
        "forensic": {"adapter": "exp_for", "anchors": ["history", "forensic"]}
    }
    return hub_inst

@pytest.mark.asyncio
async def test_triage_json_parsing_fix(hub):
    """Verify ERR-06: Type-Agnostic Triage Parser handles dict and string."""
    # 1. Test bridge_signal_clean directly
    # Use "MICE" to avoid Direct Address Force override of fuel
    raw_output = '```json\n{"addressed_to": "MICE", "fuel": 0.9, "vibe": "TEST", "intent": "STRATEGIC", "importance": 0.9, "casual": 0.1, "intrigue": 0.9}\n```'
    clean = hub.bridge_signal_clean(raw_output)
    assert isinstance(clean, dict)
    
    # Expected fuel calculation: ((1.0 - 0.1) * (0.9 + 0.9)) / 2.0 = (0.9 * 1.8) / 2 = 1.62 / 2 = 0.81
    expected_fuel = 0.81

    # 2. Mock LAB node to return this raw JSON
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=raw_output)])
    hub.residents["brain"].call_tool.return_value = MagicMock(content=[MagicMock(text="Brain response")])
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Pinky intuition")])
    
    # This should not raise TypeError: json.loads expects string
    await hub.process_query("Strategic question about silicon.")
    assert abs(hub.current_fuel - expected_fuel) < 0.01
    assert hub.residents["brain"].call_tool.called

@pytest.mark.asyncio
async def test_brain_online_callback_fix(hub):
    """Verify ERR-05: Hub uses get_vram_status() instead of brain_online()."""
    # Force brain offline via mock
    hub.get_vram_status.return_value = False
    
    # Mock lab to direct to Brain
    raw_output = '{"addressed_to": "BRAIN", "fuel": 0.8}'
    hub.residents["lab"].call_tool.return_value = MagicMock(content=[MagicMock(text=raw_output)])
    
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Pinky intuition")])
    hub.residents["shadow"].call_tool.return_value = MagicMock(content=[MagicMock(text="Shadow response")])

    # This should not raise AttributeError: 'CognitiveHub' object has no attribute 'brain_online'
    await hub.process_query("Is the brain online?")
    
    # Verify shadow was called (failover)
    assert hub.residents["shadow"].call_tool.called
