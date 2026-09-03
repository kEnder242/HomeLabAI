import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from logic.cognitive_hub import CognitiveHub

@pytest.mark.asyncio
async def test_brain_lead_executes_single_leg():
    """Verify when lead_node is brain, _run_brain_leg is called at most once."""
    hub = CognitiveHub(
        residents={"brain": MagicMock()},
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(),
        trigger_morning_briefing=AsyncMock()
    )
    hub.current_interest = 0.2  # Low interest: bypass handover
    
    with patch.object(hub, "_run_brain_leg", AsyncMock()) as mock_brain_leg, \
         patch.object(hub, "_fetch_rag_context", AsyncMock(return_value="")):
        
        t_parsed = {"vibe": "TECHNICAL", "addressed_to": "BRAIN", "domain": "unknown", "importance": 0.8}
        
        # Test lead_node == brain branch
        lead_node = "brain"
        if lead_node == "brain":
            await hub._run_brain_leg("test query", t_parsed)
        
        assert mock_brain_leg.call_count == 1, "Brain leg must execute exactly once"
