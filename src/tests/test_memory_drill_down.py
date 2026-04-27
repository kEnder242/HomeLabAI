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
    pinky.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])
    
    brain = MagicMock()
    brain.call_tool = AsyncMock()
    brain.list_tools = AsyncMock()
    brain.list_tools.return_value = MagicMock(tools=[MagicMock(name="deep_think")])
    
    archive = MagicMock()
    archive.call_tool = AsyncMock()
    archive.list_tools = AsyncMock()
    archive.list_tools.return_value = MagicMock(tools=[MagicMock(name="get_context")])
    
    return {"pinky": pinky, "brain": brain, "archive": archive}

@pytest.fixture
def hub(mock_residents):
    broadcast = AsyncMock()
    sensory = MagicMock()
    vram_status = MagicMock(return_value=True) # Brain online
    trigger_morning = AsyncMock()
    
    hub_inst = CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=vram_status,
        trigger_morning_briefing=trigger_morning,
        monitor_task_with_tics=AsyncMock(side_effect=lambda x: x)
    )
    return hub_inst

@pytest.mark.asyncio
async def test_multi_resolution_trigger(hub):
    # 1. Setup Mock Archive response
    hub.residents["archive"].call_tool.side_effect = [
        # Call 1: query_vibe
        MagicMock(content=[MagicMock(text='{"adapter": "standard", "guidance": "Standard mode."}')]),
        # Call 2: Yearly Summary
        MagicMock(content=[MagicMock(text='[YEARLY]: You worked on Montana.')]),
        # Call 3: Focal Evidence (Deep Memory Gate)
        MagicMock(content=[MagicMock(text='[FOCAL]: See 2023_04.json for PECI logs.')])
    ]
    
    # 2. Mock Triage to return RECALL intent with HIGH fuel
    hub.residents["lab"] = MagicMock()
    # importance=1.0, casual=0.0, intrigue=1.0 -> fuel=1.0
    hub.residents["lab"].call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text='{"intent": "RECALL", "vibe": "PINKY_RECALL", "importance": 1.0, "casual": 0.0, "intrigue": 1.0}')]))
    
    # 3. Mock Brain to return a dense response (satisfy Fidelity Gate)
    dense_text = "This is a very long and detailed technical response about Montana in 2023. It contains more than twenty words to ensure the Fidelity Gate is satisfied and does not trigger a recursive retry."
    hub.residents["brain"].call_tool.return_value = MagicMock(content=[MagicMock(text=dense_text)])
    
    # 4. Silence the auxiliary turns to prevent retries
    hub.execute_dispatch = AsyncMock(return_value=True)
    hub.evaluate_grounding = AsyncMock(return_value=True)
    hub.auditor = MagicMock()
    hub.auditor.audit_technical_truth = AsyncMock(return_value=True)
    
    # 5. Process query
    await hub.process_query("What did I do in 2023?")
    
    # 6. Assert Archive was called 3 times (Vibe + Yearly + Focal)
    assert hub.residents["archive"].call_tool.call_count == 3
    
    # 5. Verify Brain turn received the merged context
    calls = hub.residents["brain"].call_tool.call_args_list
    # [FEAT-295] Tooling Parity: Hub now calls 'think' for deep reasoning
    brain_task = next(c for c in calls if "think" in str(c))
    params = brain_task[0][1]
    
    assert "[YEARLY]" in params["context"]
    assert "[FOCAL]" in params["context"]
    print("\n[+] SUCCESS: Multi-Resolution Context injected into Sovereign turn.")
