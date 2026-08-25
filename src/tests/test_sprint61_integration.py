"""
[FEAT-467/468/469/470/471] Sprint 61 In-Process Integration Test Suite

Verifies the full end-to-end cascade across all Sprint 61 components:
  1. FEAT-467: Negative RAG Gateway & Zero Context Fallback
  2. FEAT-468: Multi-Agent Speaker Demarcation & Extraction
  3. FEAT-469: Epistemic Meta-Grounding & DNA Scoping
  4. FEAT-470: Pinky Critic Persona Satellite (Cartoon Quip + Agreed Summary)
  5. FEAT-471: Dynamic Runtime SpeakerRegistry Anti-Duplication
  6. Foyer Router Deep Thought Handshake routing to crosstalk
"""

import pytest
import asyncio
from unittest.mock import AsyncMock

from logic.triage_engine import (
    SpeakerRegistry,
    extract_latest_user_query,
    format_speaker_history,
    scrub_hyde_vector,
    is_meta_lexicon,
    classify_vibe_and_domain,
)
from nodes.lab_dna_router import (
    get_collection_priorities,
    filter_candidate_context,
)
from nodes.pinky_critic_persona import (
    build_critic_prompt,
    parse_critic_payload,
    format_chat_delivery,
    format_crosstalk_telemetry,
    CriticResult,
)
from src.v5.foyer.router import FoyerRouter


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SpeakerRegistry & Demarcation Integration Tests (FEAT-468, FEAT-471)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpeakerDemarcationIntegration:
    """Verifies SpeakerRegistry strips nested / redundant speaker prefixes dynamically."""

    def test_nested_demarcation_stripping(self):
        reg = SpeakerRegistry()
        dirty = "[ASSISTANT: Pinky] Pinky: [ASSISTANT: Pinky] The audio pipeline is operational."
        clean = reg.sanitize(dirty)
        assert clean == "The audio pipeline is operational."

    def test_multi_persona_stripping(self):
        reg = SpeakerRegistry()
        dirty = "Brain: Deep Thought: [ASSISTANT: Brain] VRAM is nominal."
        clean = reg.sanitize(dirty)
        assert clean == "VRAM is nominal."

    def test_user_history_demarcation_and_extraction(self):
        history = [
            {"role": "user", "name": "Jason", "content": "How is the lab running?"},
            {"role": "assistant", "name": "Brain", "content": "All nodes nominal."},
            {"role": "user", "name": "Jason", "content": "Check the audio pipeline status."}
        ]
        formatted = format_speaker_history(history)
        assert "[USER: Jason] How is the lab running?" in formatted
        assert "[ASSISTANT: Brain] All nodes nominal." in formatted
        assert "[USER: Jason] Check the audio pipeline status." in formatted

        latest = extract_latest_user_query(formatted)
        assert latest == "Check the audio pipeline status."


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Meta-Grounding & Negative RAG Gateway Integration (FEAT-467, FEAT-469)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetaGroundingAndNegativeRAG:
    """Verifies meta queries trigger DNA routing and Zero Context gate."""

    def test_meta_lexicon_detection(self):
        assert is_meta_lexicon("What is the state of the audio_pipeline?") is True
        assert is_meta_lexicon("Did the maintenance_sweeper run?") is True
        assert is_meta_lexicon("Check the override_parser status.") is True
        assert is_meta_lexicon("How does PCIe gen 5 compare to gen 4?") is False

    def test_meta_vibe_and_domain_override(self):
        query = "Can we inspect the audio_pipeline status?"
        initial_triage = {
            "vibe": "TECHNICAL",
            "domain": "standard",
            "inferred_intent": "inspecting pipeline"
        }
        vibe, domain = classify_vibe_and_domain(query, initial_triage)
        assert vibe == "META"
        assert domain == "lab_internal"

    def test_lab_dna_collection_scoping(self):
        priorities = get_collection_priorities(vibe="META", domain="lab_internal")
        assert "feature_dna" in priorities
        assert "lab_infrastructure" in priorities
        assert "career_ledger" not in priorities
        assert "behavioral_dna" not in priorities

    def test_zero_context_gate_rejection(self):
        # Best candidate distance > 0.50 -> empty context returned
        candidates = [
            {"collection": "feature_dna", "distance": 0.65, "metadata": {"feat_id": "FEAT-469"}, "document": "DNA"},
            {"collection": "lab_infrastructure", "distance": 0.70, "metadata": {}, "document": "Infra"}
        ]
        filtered = filter_candidate_context(candidates, vibe="META", domain="lab_internal", max_distance=0.50)
        assert filtered == []

    def test_zero_context_gate_acceptance_and_suppression(self):
        candidates = [
            {"collection": "feature_dna", "distance": 0.32, "metadata": {"feat_id": "FEAT-469"}, "document": "DNA routing"},
            {"collection": "career_ledger", "distance": 0.28, "metadata": {"era": "2015"}, "document": "Past resume"},
            {"collection": "lab_infrastructure", "distance": 0.40, "metadata": {"component": "vllm"}, "document": "vLLM engine"}
        ]
        filtered = filter_candidate_context(candidates, vibe="META", domain="lab_internal", max_distance=0.50)
        # career_ledger is suppressed in META vibe, feature_dna and lab_infrastructure survive
        assert len(filtered) == 2
        collections = [c["collection"] for c in filtered]
        assert "feature_dna" in collections
        assert "lab_infrastructure" in collections
        assert "career_ledger" not in collections

    def test_hyde_vector_template_scrubbing(self):
        raw_vector = "[VALIDATION]: <silicon_term_or_pcie_ras> | [STRATEGY]: <focal_goal_or_leadership_impact> | [SRE]: <bkm_scar_or_shell_command>"
        scrubbed = scrub_hyde_vector(raw_vector)
        assert "<" not in scrubbed
        assert ">" not in scrubbed

        partially_filled = "[VALIDATION]: PCIe AER error | [STRATEGY]: <focal_goal_or_leadership_impact> | [SRE]: dmesg -T"
        scrubbed = scrub_hyde_vector(partially_filled)
        assert "<" not in scrubbed
        assert "PCIe AER error" in scrubbed
        assert "dmesg -T" in scrubbed


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Pinky Critic Persona Satellite Integration (FEAT-470)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPinkyCriticPersonaIntegration:
    """Verifies critic prompt generation, JSON resilience, and chat delivery formatting."""

    def test_critic_prompt_generation(self):
        prompt = build_critic_prompt(
            user_query="How do we optimize GPU KV cache?",
            technical_summary="AWQ 4-bit quantization with vLLM PagedAttention allocation.",
            persona_name="Pinky"
        )
        assert "Pinky" in prompt
        assert "AWQ 4-bit" in prompt
        assert "banned_phrases" in prompt

    def test_critic_payload_parsing_clean(self):
        raw = '{"cartoon_retort": "Narf! Brain used 10-dollar words again.", "critique_suggestions": ["PagedAttention effectively halves VRAM footprint."]}'
        res = parse_critic_payload(raw)
        assert isinstance(res, CriticResult)
        assert "Narf" in res.cartoon_retort
        assert len(res.critique_suggestions) == 1

    def test_critic_payload_parsing_embedded(self):
        raw = 'Here is the evaluation:\n```json\n{"cartoon_retort": "Zort! Solid architecture.", "critique_suggestions": ["Zero Context gate prevents hallucination."]}\n```\nHope that helps!'
        res = parse_critic_payload(raw)
        assert res.cartoon_retort == "Zort! Solid architecture."
        assert len(res.critique_suggestions) == 1

    def test_format_chat_delivery_rejects_robotic_boilerplate(self):
        # Even if model emits "A well-crafted response", it is scrubbed out
        retort = "A well-crafted response. Egad, looks solid!"
        summary = "Well-crafted summary of the vLLM engine."
        delivery = format_chat_delivery(retort, summary)
        assert "well-crafted" not in delivery.lower()
        assert "Egad, looks solid!" in delivery

    def test_format_crosstalk_telemetry(self):
        payload = {"score": 5, "reasoning": "Sound", "slop_found": False}
        telemetry = format_crosstalk_telemetry(source="Pinky", target="Brain", payload=payload)
        assert telemetry["source"] == "Pinky"
        assert telemetry["target"] == "Brain"
        assert telemetry["payload"]["score"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FoyerRouter Preamble Stream Routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestFoyerRouterIntegration:
    """Verifies operational handshakes route to crosstalk stream."""

    @pytest.mark.asyncio
    async def test_deep_thought_preamble_routes_to_crosstalk(self):
        router = FoyerRouter(mode="SERVICE_UNATTENDED", disable_ear=True)
        router.enqueue_intent = AsyncMock()
        router.cognitive.synthesize_hyde_vector = AsyncMock(return_value="")
        broadcast_mock = AsyncMock()
        router.broadcast = broadcast_mock

        await router._spawn_deep_thought_preamble("Hello", source="WS_test", request_id="req_123")
        # Give the background task a tick to run
        await asyncio.sleep(0.05)

        # Verify broadcast was called with type="crosstalk"
        assert broadcast_mock.called
        calls = [c[0][0] for c in broadcast_mock.call_args_list if isinstance(c[0][0], dict)]
        crosstalk_calls = [c for c in calls if c.get("type") == "crosstalk"]
        assert len(crosstalk_calls) > 0
        assert any(c.get("brain_source") == "Deep Thought" for c in crosstalk_calls)
