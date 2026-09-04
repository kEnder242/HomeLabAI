"""
[FEAT-541] Test Two-Stage Zero-Duplicate RAG Cache
Verifies that:
1. Cache keys are generated deterministically.
2. Pre-triage document chunks pre-seed the cache without redundant DB calls.
3. Cache entries are reused with 0ms latency.
"""

import pytest
import hashlib
from unittest.mock import AsyncMock, MagicMock
from logic.cognitive_hub import CognitiveHub

@pytest.fixture
def mock_residents():
    archive_mock = MagicMock()
    archive_mock.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text='{"context": "Historical RAPL validation notes from 2018", "found": true}')]))
    
    lab_mock = MagicMock()
    lab_mock.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text='{"vibe": "TECHNICAL", "addressed_to": "PINKY", "importance": 0.8, "domain": "exp_tlm", "casual": 0.1, "intrigue": 0.5, "inferred_intent": "rapl"}')]))
    
    pinky_mock = MagicMock()
    pinky_mock.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text='RAPL energy status telemetry validation')]))
    
    thought_mock = MagicMock()
    thought_mock.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text='RAPL energy status telemetry validation')]))
    
    return {
        "archive": archive_mock,
        "lab": lab_mock,
        "pinky": pinky_mock,
        "brain": MagicMock(),
        "thought": thought_mock
    }

@pytest.mark.asyncio
async def test_rag_cache_pre_seeded_from_pre_triage(mock_residents):
    hub = CognitiveHub(
        mock_residents,
        lambda x: None,
        sensory_manager=None,
        get_vram_status=lambda: {"vram": "50%"},
        trigger_morning_briefing=lambda: None
    )
    
    # Simulate pre-triage document match
    hub._last_pre_triage_doc = "Pre-triage cached document from behavioral_dna collection."
    
    t_parsed = {
        "vibe": "TECHNICAL",
        "domain": "exp_bkm",
        "situation": "Test BKM lookup",
        "hints": "BKM-015"
    }
    
    # First fetch: should use pre-seeded document without calling archive node
    ctx = await hub._fetch_rag_context("tell me about BKM-015", t_parsed, n_results=1)
    assert ctx == "Pre-triage cached document from behavioral_dna collection."
    # Verify archive node was NOT called (0ms cache hit)
    mock_residents["archive"].call_tool.assert_not_called()

@pytest.mark.asyncio
async def test_rag_cache_subsequent_hit(mock_residents):
    hub = CognitiveHub(
        mock_residents,
        lambda x: None,
        sensory_manager=None,
        get_vram_status=lambda: {"vram": "50%"},
        trigger_morning_briefing=lambda: None
    )
    
    t_parsed = {
        "vibe": "TECHNICAL",
        "domain": "exp_tlm",
        "situation": "RAPL power caps",
        "hints": "RAPL"
    }
    
    # 1. First fetch: calls archive node
    ctx1 = await hub._fetch_rag_context("what is RAPL?", t_parsed, n_results=1)
    assert "Historical RAPL validation" in ctx1
    assert mock_residents["archive"].call_tool.call_count == 1
    
    # 2. Second fetch: identical turn/hyde/n_results -> must hit memory cache (0ms)
    ctx2 = await hub._fetch_rag_context("what is RAPL?", t_parsed, n_results=1)
    assert ctx2 == ctx1
    assert mock_residents["archive"].call_tool.call_count == 1  # count did NOT increase
