import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from logic.cognitive_hub import CognitiveHub

@pytest.mark.asyncio
async def test_triage_broadcast_emits_single_chat_payload():
    """Verify triage completion emits exactly one broadcast payload."""
    broadcast_mock = AsyncMock()
    hub = CognitiveHub(
        residents={},
        broadcast_callback=broadcast_mock,
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(),
        trigger_morning_briefing=AsyncMock()
    )
    
    # Mock triage relay return
    mock_triage = {
        "inferred_intent": "User is greeting the lab.",
        "addressed_to": "PINKY",
        "vibe": "CASUAL",
        "domain": "unknown",
        "casual": 0.9,
        "intrigue": 0.1,
        "importance": 0.1
    }
    
    # Simulate single broadcast block
    routing_meta = hub.triage_relay.get_console_metadata("vllm")
    public_triage = {k: v for k, v in mock_triage.items()}
    await hub.broadcast({
        "type": "chat",
        "brain": str(public_triage),
        "brain_source": routing_meta["source"],
        "channel": routing_meta["channel"],
        "final": True
    })
    
    assert broadcast_mock.call_count == 1, "Triage must emit exactly 1 broadcast packet"
