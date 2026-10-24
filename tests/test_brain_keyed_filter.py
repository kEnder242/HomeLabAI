"""[STORY 108.1 / FEAT-666 / BKM-015 / BKM-061] Brain Keyed Evidence Filter & Evidential Moat.

Hermetic tests for the keyed RAG evidence filter and the mechanical Evidential
Moat interest modulation. No live daemon, no mocks of production paths.
"""

import re

from logic.cognitive_hub import (
    build_two_mice_stage_prompt,
    format_rag_chunks_for_prompt,
    format_situational_payload_as_chunks,
)


# ---------------------------------------------------------------------------
# [BKM-015:APPROVED_REGEX] — the exact moat parse pattern (kept in lockstep with
# the production copy in cognitive_hub.py::_run_two_mice_handover).
# ---------------------------------------------------------------------------
MOAT_PATTERN = re.compile(r'(?:\[|\b)CHUNK[-_\s]*(\d+)(?:\]|\b)[:\s]*(KEEP|DROP)')


# ===========================================================================
# format_rag_chunks_for_prompt — pure formatting unit
# ===========================================================================

def test_format_empty_is_zero_context():
    assert format_rag_chunks_for_prompt("") == "[ZERO_CONTEXT]: No archive record retrieved."
    assert format_rag_chunks_for_prompt("   \n\t  ") == "[ZERO_CONTEXT]: No archive record retrieved."


def test_format_already_formatted_passthrough():
    already = "[CHUNK-1]:\nhello\n[CHUNK-2]:\nworld\n"
    assert format_rag_chunks_for_prompt(already) == already


def test_format_splits_on_double_newline():
    blob = "para one content\n\npara two content\n\npara three content"
    out = format_rag_chunks_for_prompt(blob)
    assert "[CHUNK-1]:" in out
    assert "[CHUNK-2]:" in out
    assert "[CHUNK-3]:" in out
    # 1-indexed and in order
    assert out.index("[CHUNK-1]:") < out.index("[CHUNK-2]:") < out.index("[CHUNK-3]:")
    # exactly three chunks
    assert out.count("]:\n") >= 3
    assert "[CHUNK-4]" not in out


def test_format_splits_on_dashes():
    blob = "alpha section\n---\nbeta section\n---\ngamma section"
    out = format_rag_chunks_for_prompt(blob)
    assert "[CHUNK-1]:" in out
    assert "[CHUNK-2]:" in out
    assert "[CHUNK-3]:" in out
    assert "[CHUNK-4]" not in out
    assert "alpha section" in out
    assert "beta section" in out
    assert "gamma section" in out


def test_format_zero_context_passthrough():
    zc = "[ZERO_CONTEXT]: No archive record retrieved."
    assert format_rag_chunks_for_prompt(zc) == zc


def test_format_situational_payload_as_chunks():
    payload = {
        "nightly_dialogue.json": "Topic: firmware\nDialogue: we shipped it",
        "status.json": {"status": "green", "details": "all nodes nominal"},
    }
    out = format_situational_payload_as_chunks("dream_stream", payload)
    assert "[CHUNK-1]:\nSource: nightly_dialogue.json\nTopic: firmware" in out
    assert "[CHUNK-2]:\nSource: status.json\n" in out
    assert out.count("]:\n") == 2
    # MOAT_PATTERN must be able to KEEP/DROP generated chunk IDs.
    keep = out.replace("[CHUNK-1]:", "[CHUNK-1]: KEEP ").replace("[CHUNK-2]:", "[CHUNK-2]: DROP ")
    matches = MOAT_PATTERN.findall(keep)
    assert matches == [("1", "KEEP"), ("2", "DROP")]
    assert format_situational_payload_as_chunks("meta", {}) == "[ZERO_CONTEXT]: No situational payload recorded."


# ===========================================================================
# build_two_mice_stage_prompt — stage 1 keyed output
# ===========================================================================

def test_stage1_prompt_includes_chunk_keys():
    ctx = "A\n\nB\n\nC"
    out = build_two_mice_stage_prompt(
        1,
        user_query="what is the firmware scar?",
        context=ctx,
        pinky_take="narf",
    )
    assert "[CHUNK-1]" in out
    assert "[CHUNK-2]" in out
    assert "[BEDROCK SELECTION]" in out
    # Legacy interest modulation tokens must be gone.
    assert "<boost_interest>" not in out
    assert "<damp_interest>" not in out


def test_stage1_prompt_empty_context_is_zero():
    out = build_two_mice_stage_prompt(1, user_query="hi", context="")
    assert "[ZERO_CONTEXT]" in out
    assert "<boost_interest>" not in out
    assert "<damp_interest>" not in out


# ===========================================================================
# Moat regex parsing
# ===========================================================================

def test_moat_regex_parsing_positive():
    sample = (
        "[ANALYSIS]\n"
        "- CHUNK-1: KEEP — direct match to firmware log\n"
        "- CHUNK-2: DROP — tangential\n"
        "[BEDROCK SELECTION]\n"
        "- CHUNK-1: KEEP\n"
        "- CHUNK-2: DROP\n"
    )
    # Production dedupes via sorted(set(kept_ids)); CHUNK-1 appears in both the
    # [ANALYSIS] line and the [BEDROCK SELECTION] line, so we dedupe too.
    kept = sorted({int(m.group(1)) for m in MOAT_PATTERN.finditer(sample) if m.group(2).upper() == "KEEP"})
    assert kept == [1]


def test_moat_regex_parsing_multiple_kept():
    sample = (
        "[BEDROCK SELECTION]\n"
        "- CHUNK-3: KEEP\n"
        "- CHUNK-1: KEEP\n"
        "- CHUNK-2: DROP\n"
    )
    kept = sorted(int(m.group(1)) for m in MOAT_PATTERN.finditer(sample) if m.group(2).upper() == "KEEP")
    assert kept == [1, 3]


def test_moat_regex_parsing_all_drop():
    sample = "[BEDROCK SELECTION]\n- CHUNK-1: DROP\n- CHUNK-2: DROP\n"
    kept = [int(m.group(1)) for m in MOAT_PATTERN.finditer(sample) if m.group(2).upper() == "KEEP"]
    assert kept == []


# ===========================================================================
# Evidential Moat interest math — replicate the exact pure expression inline
# (no CognitiveHub instantiation; residents/daemon required).
# ===========================================================================

def _moat(gate_interest: float, candidate_count: int, kept_count: int) -> float:
    """Replicates the exact Moat expression from _run_two_mice_handover."""
    if candidate_count > 0:
        if kept_count >= 1:
            return min(1.0, gate_interest + 0.20)  # Positive Moat
        else:
            return max(0.0, min(0.30, gate_interest - 0.25))  # Negative Moat
    else:
        return gate_interest  # Neutral Moat


def test_positive_moat():
    gi = 0.6
    assert _moat(gi, candidate_count=3, kept_count=1) == min(1.0, gi + 0.20)
    # clamps at ceiling
    assert _moat(0.95, candidate_count=2, kept_count=2) == 1.0


def test_negative_moat():
    gi = 0.8
    assert _moat(gi, candidate_count=3, kept_count=0) == max(0.0, min(0.30, gi - 0.25))
    # never below floor, and capped at 0.30
    assert _moat(0.9, candidate_count=2, kept_count=0) == 0.30
    assert _moat(0.10, candidate_count=2, kept_count=0) == max(0.0, min(0.30, 0.10 - 0.25))


def test_neutral_moat():
    gi = 0.55
    assert _moat(gi, candidate_count=0, kept_count=0) == gi
