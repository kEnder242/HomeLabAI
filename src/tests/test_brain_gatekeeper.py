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
