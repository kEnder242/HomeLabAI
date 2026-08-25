import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from logic.cognitive_hub import CognitiveHub


def mock_resp(text):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    return m


@pytest.mark.asyncio
async def test_speculative_prefetch_consumed_when_interest_high():
    """[FEAT-457] Verify Brain consumes pre-fetched context when interest > 0.5."""
    pinky = MagicMock()
    pinky.call_tool = AsyncMock(return_value=mock_resp("Narf! Looking into PCIe AER."))

    brain = MagicMock()
    brain.call_tool = AsyncMock(return_value=mock_resp("Brain analysis of PCIe registers."))

    archive = MagicMock()
    archive.call_tool = AsyncMock(return_value=mock_resp('{"text": "PCIe AER context", "sources": ["2024.json"]}'))

    lab = MagicMock()
    lab.call_tool = AsyncMock(return_value=mock_resp(json.dumps({
        "importance": 0.9, "casual": 0.1, "intrigue": 0.9,
        "vibe": "TECHNICAL", "intent": "RECALL",
        "addressed_to": "PINKY", "hints": "PCIe AER"
    })))

    residents = {
        "pinky": pinky,
        "brain": brain,
        "archive": archive,
        "lab": lab
    }

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(return_value=True),
        trigger_morning_briefing=AsyncMock()
    )
    hub.auditor = MagicMock(audit_technical_truth=AsyncMock(return_value=True))

    fetch_mock = AsyncMock(return_value="Prefetched PCIe AER context")
    hub._fetch_rag_context = fetch_mock
    hub._run_brain_leg = AsyncMock()

    await hub.process_query("Tell me about PCIe AER registers")

    # Verify RAG context was fetched speculatively
    assert fetch_mock.called, "RAG context must be fetched speculatively during Turn 1"
    # Verify _run_brain_leg was called with prefetch_task
    assert hub._run_brain_leg.called, "_run_brain_leg must be called when interest > 0.5"
    call_kwargs = hub._run_brain_leg.call_args.kwargs
    assert "prefetch_task" in call_kwargs, "prefetch_task must be passed to _run_brain_leg"


@pytest.mark.asyncio
async def test_speculative_prefetch_cancelled_when_interest_low():
    """[FEAT-457] Verify pre-fetched context is preempted/cancelled when interest <= 0.5."""
    pinky = MagicMock()
    pinky.call_tool = AsyncMock(return_value=mock_resp("Narf! Hello."))

    lab = MagicMock()
    lab.call_tool = AsyncMock(return_value=mock_resp(json.dumps({
        "importance": 0.1, "casual": 0.9, "intrigue": 0.1,
        "vibe": "CASUAL", "intent": "CHAT",
        "addressed_to": "PINKY", "hints": ""
    })))

    residents = {
        "pinky": pinky,
        "brain": MagicMock(call_tool=AsyncMock()),
        "archive": MagicMock(call_tool=AsyncMock()),
        "lab": lab
    }

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(return_value=True),
        trigger_morning_briefing=AsyncMock()
    )
    hub.auditor = MagicMock(audit_technical_truth=AsyncMock(return_value=True))

    fetch_mock = AsyncMock(return_value="Prefetched context")
    hub._fetch_rag_context = fetch_mock
    hub._run_brain_leg = AsyncMock()

    await hub.process_query("hi")

    # Verify Brain leg was NOT called
    assert not hub._run_brain_leg.called, "Brain leg must not run when interest is low (preempted)"
