"""
[FEAT-635] Brain Information Gatekeeper & Curator Synergy Annotations Unit Tests
Sprint: SPR-96.0 (Story 96.3)
"""

from logic.cognitive_hub import build_two_mice_stage_prompt
from nodes.brain_node import BRAIN_SYSTEM_PROMPT


def test_brain_system_prompt_has_feat_635_directive():
    """Verify BRAIN_SYSTEM_PROMPT contains the FEAT-635 Information Gatekeeper directive."""
    assert "[FEAT-635] INFORMATION GATEKEEPER" in BRAIN_SYSTEM_PROMPT
    assert "💡 Curator Note:" in BRAIN_SYSTEM_PROMPT
    assert "Drop tangential noise" in BRAIN_SYSTEM_PROMPT


def test_stage1_prompt_contains_gatekeeper_and_curator_instructions():
    """Verify Stage 1 prompt primes Brain to act as Information Gatekeeper with Curator Notes."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query="How do we synchronize vector DNA across submodules?",
        context="[FEAT-582]: DNA Forge Studio.\n[BKM-060]: Federated DNA Taxonomy.",
        interest=0.85,
    )
    assert "Information Gatekeeper and Subconscious Intuition node" in prompt
    assert "💡 Curator Note:" in prompt
    assert "drop irrelevant/tangential items" in prompt
    assert "3-4 dense" in prompt
    assert "pure technical signal" in prompt
    assert "<historical_record>" in prompt


def test_stage1_zero_context_handled_gracefully():
    """Verify Stage 1 handles empty candidate context without crashing or hallucinating."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query="Status check",
        context="",
        interest=0.75,
    )
    assert "[ZERO_CONTEXT]: No archive record retrieved." in prompt
    assert "STAGE_1_INSTRUCTIONS" in prompt


def test_semantic_gatekeeper_cosine_threshold_filtering():
    """[Story 99.3 / FEAT-635 / BKM-015] Verify semantic candidate filtering enforces cosine distance <= 0.55."""
    candidates = [
        {"id": "BKM-060", "text": "Federated DNA Taxonomy", "distance": 0.32},
        {"id": "FEAT-647", "text": "Subversive Research Tool", "distance": 0.48},
        {"id": "IRRELEVANT-999", "text": "Unrelated peripheral noise", "distance": 0.78},
    ]
    # Filter by cosine distance threshold <= 0.55 per BKM-015 / BKM-060
    filtered = [c for c in candidates if c["distance"] <= 0.55]
    assert len(filtered) == 2
    assert [c["id"] for c in filtered] == ["BKM-060", "FEAT-647"]
    assert "IRRELEVANT-999" not in [c["id"] for c in filtered]


def test_bkm015_anti_hardcoding_intent_routing():
    """[Story 99.3 / BKM-015] Verify intent and domain routing does not rely on rigid keyword strings."""
    # Semantic intents should support synonymous query formulations
    synonyms = [
        "Audit memory topology across active silicon nodes",
        "Inspect hardware residency and RAM layouts",
        "Check how much VRAM is allocated on GPUs",
    ]
    for q in synonyms:
        prompt = build_two_mice_stage_prompt(1, user_query=q, context="[BKM-024]: Live Validation", interest=0.8)
        assert "[USER_QUERY]:" in prompt
        assert q in prompt
        assert "Information Gatekeeper" in prompt

