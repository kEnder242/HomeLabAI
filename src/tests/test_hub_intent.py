import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, ANY
from src.logic.cognitive_hub import CognitiveHub

@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    # Mock list_tools to return something valid for the Hub Hallucination Detection
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
    
    # Correctly mock monitor_task_with_tics as a pass-through that awaits
    async def monitor_pass_through(coro):
        return await coro
    monitor = AsyncMock(side_effect=monitor_pass_through)
    
    hub_inst = CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        brain_online_callback=brain_online,
        get_oracle_signal_callback=get_oracle,
        monitor_task_with_tics_callback=monitor
    )
    # [FIX] Manually inject anchors for test isolation
    hub_inst.intent_anchors = {
        "telemetry": {"adapter": "exp_tlm", "anchors": ["telemetry", "thermal", "rapl"]},
        "architecture": {"adapter": "exp_bkm", "anchors": ["architecture", "bkm"]},
        "forensic": {"adapter": "exp_for", "anchors": ["history", "forensic"]}
    }
    return hub_inst

@pytest.mark.asyncio
async def test_is_casual_detection(hub):
    # Tests the internal logic of process_query indirectly
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    # "Hi" should be casual
    await hub.process_query("Hi")
    # Verify Pinky was called with facilitate
    hub.residents["pinky"].call_tool.assert_called_with("facilitate", ANY)
    
    hub.residents["pinky"].call_tool.reset_mock()
    
    # "What is the meaning of life?" (6 words) should be strategic
    await hub.process_query("What is the meaning of life?")
    # For strategic, it calls pinky.facilitate with STRATEGIC_INTENT context
    calls = hub.residents["pinky"].call_tool.call_args_list
    assert any("STRATEGIC_INTENT" in str(c) for c in calls)

@pytest.mark.asyncio
async def test_casual_keywords(hub):
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    # "Narf!" is a keyword
    await hub.process_query("Narf!")
    hub.residents["pinky"].call_tool.assert_called_once()
    assert "facilitate" in hub.residents["pinky"].call_tool.call_args[0]
    # call_args[0][1] is the params dict
    assert "GREETING" in hub.residents["pinky"].call_tool.call_args[0][1]["context"]

@pytest.mark.asyncio
async def test_strategic_delegation(hub):
    hub.execute_dispatch = AsyncMock(return_value=True)
    
    # Mock Pinky's facilitate to return an interjection
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="I should ask the Brain.")])
    # Mock Brain's deep_think to return a result
    hub.residents["brain"].call_tool.return_value = MagicMock(content=[MagicMock(text="The result of the analysis.")])
    
    # "thermal profile" should map to exp_tlm now
    await hub.process_query("Analyze the thermal profile of the 2080 Ti")
    
    # Should call Pinky for intuition
    assert hub.residents["pinky"].call_tool.called
    # Should call Brain for deep_think
    assert hub.residents["brain"].call_tool.called
    
    hub.residents["brain"].call_tool.assert_called_with("deep_think", {"task": ANY, "metadata": {"expert_adapter": "exp_tlm"}})

@pytest.mark.asyncio
async def test_expert_routing_telemetry(hub):
    hub.execute_dispatch = AsyncMock(return_value=True)
    hub.residents["pinky"].call_tool.return_value = MagicMock(content=[MagicMock(text="Checking telemetry.")])
    hub.residents["brain"].call_tool.return_value = MagicMock(content=[MagicMock(text="Dense enough response for fidelity gate.")])
    
    await hub.process_query("Check the telemetry for the last run")
    hub.residents["brain"].call_tool.assert_called_with("deep_think", {"task": ANY, "metadata": {"expert_adapter": "exp_tlm"}})
