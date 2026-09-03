import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from logic.cognitive_hub import CognitiveHub

@pytest.mark.asyncio
async def test_resolve_hyde_vector_suppresses_unknown_domain():
    """Verify resolve_hyde_vector returns empty string when domain is unknown."""
    hub = CognitiveHub(
        residents={},
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(),
        trigger_morning_briefing=AsyncMock()
    )
    triage_result = {
        "inferred_intent": "User is greeting the lab.",
        "addressed_to": "PINKY",
        "vibe": "CASUAL",
        "domain": "unknown",
        "importance": 0.1
    }
    hyde, tier = await hub.resolve_hyde_vector("hello pinky", triage_result)
    assert hyde == "", "HyDE vector must be empty for domain='unknown'"

@pytest.mark.asyncio
async def test_fetch_rag_context_bypasses_chromadb_on_empty_hyde():
    """Verify _fetch_rag_context returns empty string when HyDE is empty."""
    hub = CognitiveHub(
        residents={"archive": MagicMock()},
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(),
        trigger_morning_briefing=AsyncMock()
    )
    with patch.object(hub, "resolve_hyde_vector", AsyncMock(return_value=("", "DIRECT_RAW_QUERY"))):
        rag_context = await hub._fetch_rag_context("hello pinky", {"domain": "unknown"})
        assert rag_context == "", "RAG context must be empty when HyDE is empty"
