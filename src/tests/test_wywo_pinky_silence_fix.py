import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from logic.cognitive_hub import CognitiveHub


@pytest.mark.asyncio
async def test_wywo_pinky_stage2_and_rag_accordion_emitted():
    """Verify that WYWO queries emit Pinky Stage 2 opening take and the RAG accordion."""
    packets = []

    async def fake_broadcast(pkt):
        packets.append(pkt)

    residents = {
        "brain": MagicMock(),
        "pinky": MagicMock(),
        "thought": MagicMock(),
        "archive": MagicMock(),
        "lab": MagicMock(),
    }
    for r in residents.values():
        r.call_tool = AsyncMock()
        r.list_tools = AsyncMock()

    # Mock archive get_context for subconscious dreams
    wisdom_response = MagicMock()
    wisdom_response.content = [MagicMock(text="Dream context: System synthesis nominal.")]
    residents["archive"].call_tool.return_value = wisdom_response

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=fake_broadcast,
        sensory_manager=MagicMock(),
        get_vram_status=lambda: True,
        trigger_morning_briefing=AsyncMock(),
    )

    t_parsed = {
        "vibe": "WYWO",
        "domain": "acme_lab_history",
        "situation": "Checking overnight logs",
        "hints": "none",
        "importance": 0.8,
        "intrigue": 0.8,
        "addressed_to": "NONE",
        "target_domains": ["dream_stream"],
    }

    # Mock resolve_hyde_vector to simulate Pinky Stage 2 scout output
    async def fake_resolve_hyde(query, triage_result, timeout=8.0, request_id="default"):
        triage_result["_hyde_resolved"] = True
        triage_result["_hyde_tier"] = "pinky_local_vllm"
        triage_result["hyde_vector_text"] = "Acme Lab 2026 overnight standup"
        # Pinky Stage 2 greeting broadcast
        await fake_broadcast({
            "type": "thought_stream",
            "source": "Pinky (Triage)",
            "channel": "voice",
            "console": "Left",
            "token": "Hey Jason, checking what we talked about last night!",
            "final": False,
            "request_id": request_id,
        })
        return "Acme Lab 2026 overnight standup", "pinky_local_vllm"

    with patch.object(hub, "step_triage", new=AsyncMock(return_value=t_parsed)), \
         patch.object(hub, "resolve_hyde_vector", side_effect=fake_resolve_hyde), \
         patch.object(hub, "_run_two_mice_handover", new=AsyncMock(return_value=True)):

        await hub.process_query("What did you guys talk about last night?", request_id="test_wywo_fix")

    # 1. Assert Pinky Stage 2 Opening Take was broadcast
    pinky_scout_pkts = [
        p for p in packets
        if p.get("source") == "Pinky (Triage)" and p.get("console") == "Left"
    ]
    assert len(pinky_scout_pkts) > 0, "Pinky Stage 2 opening take packet was not emitted"
    assert "Hey Jason" in pinky_scout_pkts[0]["token"]

    # 2. Assert RAG Accordion packet was emitted for WYWO situational chunks
    rag_eval_pkts = [p for p in packets if p.get("type") == "rag_eval"]
    assert len(rag_eval_pkts) == 1, f"Expected 1 rag_eval packet, got {len(rag_eval_pkts)}"
    eval_pkt = rag_eval_pkts[0]
    assert eval_pkt["doc_id"] == "dream_stream"
    assert eval_pkt["channel"] == "chat"
    assert eval_pkt["brain_source"] == "Pinky (Scout)"
    assert eval_pkt["vibe"] == "WYWO"
    assert len(eval_pkt["full_context"]) > 0
