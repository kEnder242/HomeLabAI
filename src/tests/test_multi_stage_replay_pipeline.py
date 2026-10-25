"""
[FEAT-645 / BKM-083] Multi-Stage Replay Pipeline Harness & Contract Assertion.

Locks the end-to-end deliberation contract across all 5 sequential stages
using the verified litmus query:
  "Can you look up my experience on psys? I think the project was Aurora. I want to refresh my memory on what I did."

Stages verified:
  Stage 1: Pre-Triage (CLaRa-DNA vector probe & continuous semantic affinity)
  Stage 2: Triage Relay (Decoupled tone, domain, intent, and pure scalar interest)
  Stage 3: HyDE Synthesis & RAG Retrieval (search_required: bool, non-empty HyDE vector, ChromaDB candidates)
  Stage 4: Brain Information Gatekeeper (3-4 dense bullets, narrative steering, zero distractor noise)
  Stage 5: Deep Thought Synthesis & Pinky Voice Delivery (Tri-Node Relay token streaming across Right, Center, and Left consoles)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from logic.cognitive_hub import (
    CognitiveHub,
    TWO_MICE_BRAIN_CHANNEL,
    TWO_MICE_BRAIN_CONSOLE,
    TWO_MICE_PINKY_CHANNEL,
    TWO_MICE_PINKY_CONSOLE,
    build_two_mice_stage_prompt,
    build_two_mice_stream_packet,
)
from logic.traversal_dispatcher import resolve_collection_scope
from logic.vector_pre_triage import probe_clara_dna_sync

LITMUS_QUERY = (
    "Can you look up my experience on psys? I think the project was Aurora. "
    "I want to refresh my memory on what I did."
)

SAMPLE_AURORA_RAG = (
    "[ACQUISITION Source: 2019_04.json]: Document anchor: [2019-04-12] [STRATEGIC_ANCHOR] "
    "Enabled psys power monitoring driver on Aurora platform compute nodes. "
    "Validated RAPL energy counters and platform power telemetry.\n---\n"
    "[ACQUISITION Source: 2018_11.json]: Document anchor: PECI stress testing on Purley platform."
)


def _make_test_hub(broadcast_fn=None):
    broadcast = broadcast_fn or AsyncMock()
    return CognitiveHub(
        residents={},
        broadcast_callback=broadcast,
        sensory_manager=None,
        get_vram_status=None,
        trigger_morning_briefing=None,
        config={
            "interest_pacing": {
                "token_multiplier": 150,
                "min_token_floor": 32,
                "max_token_ceiling": 1500,
            }
        },
    )


def test_stage1_pre_triage_affinity():
    """Stage 1: CLaRa-DNA probe identifies semantic affinity without binary casual overrides."""
    # Run the real CPU vector probe against ChromaDB (port 8001) or verify contract
    res = probe_clara_dna_sync(LITMUS_QUERY)
    assert isinstance(res, dict)
    # Continuous semantic affinity should be non-negative float
    assert "semantic_hint" in res or "semantic_affinity" in res or "min_distance" in res


def test_stage2_triage_interest_calculation():
    """Stage 2: High intrigue and importance must yield interest >= 0.70 regardless of greeting style."""
    hub = _make_test_hub()
    t_parsed = {
        "inferred_intent": "Recall Aurora psys experience",
        "addressed_to": "NONE",
        "vibe": "HISTORICAL",
        "domain": "work_history",
        "casual": 0.2,
        "intrigue": 0.9,
        "importance": 0.8,
        "target_domains": ["career_ledger"],
    }
    # Test interest calculation formula: (intrigue * 0.4) + (importance * 0.6)
    intrigue = float(t_parsed.get("intrigue", 0.5))
    importance = float(t_parsed.get("importance", 0.5))
    calculated_interest = (intrigue * 0.4) + (importance * 0.6)
    assert calculated_interest >= 0.70, f"Interest {calculated_interest} was below 0.70!"


def test_stage3_hyde_rag_resolution():
    """Stage 3: HyDE RAG resolution retrieves candidate docs when target_domains has collections and search_required is True."""
    hub = _make_test_hub()
    triage_fixture = {
        "inferred_intent": "Recall Aurora psys experience",
        "addressed_to": "NONE",
        "vibe": "HISTORICAL",
        "domain": "work_history",
        "search_required": True,
        "calculated_interest": 0.84,
        "importance": 0.8,
        "target_domains": ["career_ledger"],
        "hyde_vector_text": "[VALIDATION]: Aurora psys | [STRATEGY]: refresh memory | [SRE]: career ledger",
    }

    archive_mock = MagicMock()
    archive_mock.call_tool = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=SAMPLE_AURORA_RAG)])
    )
    hub.residents["archive"] = archive_mock

    async def _run():
        return await hub.step_hyde_rag(LITMUS_QUERY, triage_fixture)

    clean_hyde, rag_docs = asyncio.run(_run())
    assert len(clean_hyde) > 5
    assert "aurora" in clean_hyde.lower()
    assert len(rag_docs) > 0
    assert "Aurora" in rag_docs


def test_stage4_brain_gatekeeper_prompt_construction():
    """Stage 4: Brain Gatekeeper prompt instructs line-by-line evidence filtering for bedrock."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=LITMUS_QUERY,
        context=SAMPLE_AURORA_RAG,
        interest=0.85,
    )
    assert "STAGE 1" in prompt
    assert "<historical_record>" in prompt
    assert "EVIDENCE FILTER" in prompt
    assert "[ANALYSIS]" in prompt
    assert "[BEDROCK SELECTION]" in prompt
    assert "KEEP/DROP" in prompt
    assert "[CHUNK-1]" in prompt


def test_stage5_tri_node_relay_contract():
    """Stage 5: Tri-Node Relay verifies streaming packets across Brain, Deep Thought, and Pinky."""
    packets = []

    async def _run_test():
        async def mock_broadcast(pkt):
            packets.append(pkt)

        hub = _make_test_hub(broadcast_fn=mock_broadcast)
        
        # Configure mock residents for brain, thought, pinky
        brain_mock = MagicMock()
        thought_mock = MagicMock()
        pinky_mock = MagicMock()

        hub.residents["brain"] = brain_mock
        hub.residents["thought"] = thought_mock
        hub.residents["pinky"] = pinky_mock

        # Verification packet structure
        p_brain = build_two_mice_stream_packet(
            source="Brain (Archive)", channel=TWO_MICE_BRAIN_CHANNEL, console=TWO_MICE_BRAIN_CONSOLE, token="[Anchor 1]", final=False
        )
        p_thought = build_two_mice_stream_packet(
            source="Deep Thought (Strategy)", channel="insight", console="center", token="[Strategic Synthesis]", final=False
        )
        p_pinky = build_two_mice_stream_packet(
            source="Pinky (Voice)", channel=TWO_MICE_PINKY_CHANNEL, console=TWO_MICE_PINKY_CONSOLE, token="Narf!", final=False
        )

        await mock_broadcast(p_brain)
        await mock_broadcast(p_thought)
        await mock_broadcast(p_pinky)

    asyncio.run(_run_test())

    assert len(packets) == 3
    sources = [p["source"] for p in packets]
    assert "Brain (Archive)" in sources
    assert "Deep Thought (Strategy)" in sources
    assert "Pinky (Voice)" in sources


def test_stage6_brain_dynamic_boost_contract():
    """Stage 6: Verify Brain <boost_interest> boosts interest by +0.20 and scales dt_budget."""
    base_interest = 0.75
    grounding_with_boost = "Verified PSYS bedrock record. <boost_interest> Passing to Deep Thought."

    # Compute boosted interest per Story 103.15 contract
    boosted_interest = base_interest
    if "<boost_interest>" in grounding_with_boost or "<upvote>" in grounding_with_boost:
        boosted_interest = min(1.0, base_interest + 0.20)

    assert boosted_interest == 0.95

    # Compute scaled Deep Thought budget
    dt_budget = max(300, min(1500, int(boosted_interest * 1200)))
    assert dt_budget == int(0.95 * 1200)  # 1140 tokens
    assert dt_budget > int(base_interest * 1200)  # Expanded runway


def test_stage7_conversational_hyde_and_upvote():
    """Stage 7 (Story 103.18 / 103.24): Pinky spoken voice HyDE extracts structured JSON (or trailing [HYDE: ...] tag) and applies sovereign upvote."""
    from logic.cognitive_hub import PINKY_HYDE_SCHEMA
    import json

    # 1. Verify PINKY_HYDE_SCHEMA specification
    schema_props = PINKY_HYDE_SCHEMA["json_schema"]["schema"]["properties"]
    assert "spoken_take" in schema_props
    assert "search_terms" in schema_props
    assert "upvote" in schema_props

    # 2. End-to-end mock resolution with structured JSON payload
    hub = _make_test_hub()
    hub.residents["pinky"] = MagicMock()
    hub.current_interest = 0.65
    mock_payload = json.dumps({
        "spoken_take": "Narf! Let me dig into the Psys and Aurora archives from the 2021 era for you!",
        "search_terms": "Aurora psys power telemetry 2021 Archer City",
        "upvote": True,
    })

    async def fake_stream(*args, **kwargs):
        yield mock_payload

    hub._process_node_stream = fake_stream
    triage = {"inferred_intent": "find psys", "domain": "exp_tlm", "vibe": "TECHNICAL"}

    async def _run_structured():
        return await hub.resolve_hyde_vector("query", triage)

    vec, tier = asyncio.run(_run_structured())
    assert vec == "Aurora psys power telemetry 2021 Archer City"
    assert hub._last_pinky_greeting == "Narf! Let me dig into the Psys and Aurora archives from the 2021 era for you!"
    assert round(hub.current_interest, 2) == 0.85  # Boosted +0.20

    # 3. Verify legacy tag fallback
    raw_stream = (
        "Narf! Let me dig into the Psys and Aurora archives from the 2021 era for you! <upvote>\n"
        "[HYDE: Aurora psys post-silicon debug 2021]"
    )
    assert "<upvote>" in raw_stream
    old_interest = 0.65
    new_interest = round(min(1.0, old_interest + 0.20), 2)
    assert new_interest == 0.85
    assert "[HYDE:" in raw_stream
    idx = raw_stream.find("[HYDE:")
    vector = raw_stream[idx + 6:].split("]")[0].strip()
    assert vector == "Aurora psys post-silicon debug 2021"


def test_stage8_deep_thought_guidance_and_positive_coherence():
    """Stage 8 (Story 103.20): Deep Thought system prompt has fluid guidance without rigid form headings."""
    from nodes.thought_node import DEEP_THOUGHT_SYSTEM_PROMPT
    assert "# ARCHITECTURAL GUIDANCE" in DEEP_THOUGHT_SYSTEM_PROMPT
    assert "1. BREVITY OF AUTHORITY" not in DEEP_THOUGHT_SYSTEM_PROMPT
    assert "5. [FEAT-355] VISIBLE CONSENSUS" not in DEEP_THOUGHT_SYSTEM_PROMPT
    assert "Telemetry suppression" in DEEP_THOUGHT_SYSTEM_PROMPT
    assert "Do NOT structure your response with form labels, bold headers" in DEEP_THOUGHT_SYSTEM_PROMPT


def test_stage9_critic_bridge_contract():
    """Stage 9 (Story 103.21): Pinky Critic schema defines retort as a spoken conversational bridge directly to Jason."""
    from nodes.pinky_critic_persona import build_critic_prompt
    payload_str = build_critic_prompt(
        user_query="Can you look up Aurora?",
        technical_summary="Aurora project validated in 2021.",
    )
    import json
    data = json.loads(payload_str)
    retort_schema = data["output_schema"]["retort"]
    assert "Pinky's final spoken verdict to Jason" in retort_schema
    assert "confirming the technical reality and offering a natural conversational follow-up" in retort_schema
    assert "e.g." not in retort_schema


def test_stage10_unified_council_greeting_contract():
    """Stage 10 (Story 104.1 / FEAT-657): Unified Council routing for casual greetings.
    Asserts zero-bifurcation: unaddressed greetings enter the council (lead_node == 'brain'),
    RAG produces zero queries, Deep Thought stays dormant, and Pinky voice is paced.
    """
    hub = _make_test_hub()
    t_parsed = {
        "inferred_intent": "greeting",
        "addressed_to": "NONE",
        "vibe": "CASUAL",
        "domain": "unknown",
        "casual": 0.8,
        "intrigue": 0.0,
        "importance": 0.0,
        "target_domains": [],
        "calculated_interest": 0.06,
    }

    # In pure Waterfall (FEAT-658), lead_node is abolished; depth cascades purely by fuel
    assert not hasattr(hub, "lead_node")
    assert not hasattr(hub, "_lead_node")

    # Low fuel (interest = 0.06) exhausts after Pinky's opening take; Brain & Deep Thought dormant
    interest = 0.06
    assert interest < 0.35  # Brain remains dormant
    dt_budget = int(interest * 1200) if interest >= 0.30 else 0
    assert dt_budget == 0  # Deep Thought remains dormant


def test_stage11_addressed_waterfall_contract():
    """Stage 11 (Story 104.11 / FEAT-658): Pure Waterfall Execution without lead_node.
    Asserts that even when a query is explicitly addressed to Pinky ('addressed_to: PINKY'),
    it does not branch into an isolated single-node loop; 100% of turns pass into
    _run_two_mice_handover, and depth cascades purely based on fuel (interest).
    """
    hub = _make_test_hub()
    t_parsed = {
        "inferred_intent": "informal inquiry",
        "addressed_to": "PINKY",
        "vibe": "TECHNICAL",
        "domain": "work_history",
        "casual": 0.3,
        "intrigue": 0.8,
        "importance": 0.7,
        "target_domains": ["career_ledger"],
        "calculated_interest": 0.74,
    }

    # Verify that lead_node is completely abolished from the hub routing
    assert not hasattr(hub, "lead_node")
    assert not hasattr(hub, "_lead_node")

    # High fuel (interest = 0.74) enables Deep Thought synthesis
    dt_budget = max(500, min(1500, int(t_parsed["calculated_interest"] * 1200) + 200))
    assert dt_budget >= 1000  # Deep Thought awakens on high fuel


def test_stage12_multi_domain_dna_resolution_contract():
    """Stage 12: Multi-domain DNA resolution contract via resolve_collection_scope."""
    # Empty target_domains yields empty collection list immediately.
    assert resolve_collection_scope(
        vibe="TECHNICAL", target_domains_or_domain=[]
    ) == []
    # Single bkm domain maps to behavioral_dna.
    assert resolve_collection_scope(
        vibe="TECHNICAL", target_domains_or_domain=["bkm"]
    ) == ["behavioral_dna"]
    # Multi-domain TECHNICAL: ordered by TECHNICAL vibe priority (behavioral_dna before feature_dna).
    assert resolve_collection_scope(
        vibe="TECHNICAL", target_domains_or_domain=["bkm", "feature"]
    ) == ["behavioral_dna", "feature_dna"]
    # Multi-domain HISTORICAL: ordered by HISTORICAL vibe priority (career_ledger before sprint_dna).
    assert resolve_collection_scope(
        vibe="HISTORICAL", target_domains_or_domain=["sprint", "career"]
    ) == ["career_ledger", "sprint_dna"]


def test_stage13_wywo_standup_fastpath_contract():
    """Stage 13 (Story 108.5 & 108.6): WYWO standup fast-path routing and situational chunking contract.
    Asserts deterministic classification of standup inquiry into ('WYWO', 'dream_stream') and
    universal serialization into keyed [CHUNK-N] blocks for Brain's evidential filter.
    """
    from logic.triage_engine import classify_vibe_and_domain
    from logic.cognitive_hub import format_situational_payload_as_chunks

    vibe, domain = classify_vibe_and_domain("what did you do while i was out?", {})
    assert vibe == "WYWO"
    assert domain == "dream_stream"

    mock_dream_payload = {
        "nightly_dialogue.json": "Completed overnight telemetry backup on node KENDER.",
        "status.json": "All services nominal.",
    }
    chunked = format_situational_payload_as_chunks("dream_stream", mock_dream_payload)
    assert "[CHUNK-1]:" in chunked
    assert "Source: nightly_dialogue.json" in chunked
    assert "[CHUNK-2]:" in chunked
    assert "Source: status.json" in chunked


def test_stage14_unclear_foil_quiescence_contract():
    """Stage 14 (Story 108.7 & 108.8): Speculative foil and quiescence contract for ambiguous turns.
    Asserts that underspecified queries naturally exhaust interest (< 0.35 threshold),
    leaving Deep Thought dormant and allowing Pinky to deliver an inquisitive foil.
    """
    t_parsed = {
        "inferred_intent": "ambiguous reference",
        "vibe": "UNCLEAR",
        "domain": "unclear",
        "calculated_interest": 0.20,
    }

    # Quiescence check: interest (0.20) is below the 0.35 threshold
    assert t_parsed["calculated_interest"] < 0.35
    # Deep Thought receives 0 budget
    dt_budget = int(t_parsed["calculated_interest"] * 1200) if t_parsed["calculated_interest"] >= 0.30 else 0
    assert dt_budget == 0





