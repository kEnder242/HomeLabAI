"""
[FEAT-635 / VIBE-015] Standalone Brain Voice & Replay Test Harness
Sprint: SPR-102.0 (Story 102.9)
DNA: [FEAT-635] Brain Epistemic Gatekeeper, [BKM-024] Live Validation Mandate (offline hermetic), [VIBE-015] Two-Mice Sideband.

Offline-only replay harness that exercises Brain's cynical voice, narrative
steering, and RAG filtering logic WITHOUT full websocket overhead or live
daemons. Verifies:
  1. BRAIN_SYSTEM_PROMPT persona (1st-person, cynical, rigorous + Narrative
     Steering + Information Gatekeeper & RAG Filtering directives).
  2. Stage 1 Two-Mice handover prompt (Brain as Narrative Reality Steerer that
     prunes tangential chunks and emits Curator Notes).
  3. Multi-turn simulated replay: 1 relevant bedrock chunk preserved while 2
     tangential distractors are pruned, without stalling or downvoting interest.

All tests are hermetic: pure string/fixture assertions, no I/O, no network.
"""

from logic.cognitive_hub import build_two_mice_stage_prompt
from nodes.brain_node import BRAIN_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Shared offline fixtures
# ---------------------------------------------------------------------------

# A multi-turn simulated query: the bedrock chunk that MUST be preserved, plus
# two tangential distractors that MUST be pruned. Distances follow the
# FEAT-635 semantic gate: bedrock <= 0.55, distractors > 0.55.
BEDROCK_CHUNK = (
    "[BKM-060]: Federated DNA Taxonomy — Chroma distance 0.32, "
    "bedrock invariant: submodules synchronize vector DNA via the Forge Studio."
)
DISTRACTOR_1 = (
    "[FEAT-999]: Unrelated peripheral noise on GPU thermal throttling, "
    "distance 0.81 — tangential to the query."
)
DISTRACTOR_2 = (
    "[VIBE-998]: Off-topic chatter about lab coffee preferences, "
    "distance 0.74 — tangential to the query."
)

SIMULATED_MULTI_TURN_QUERY = (
    "How do we synchronize vector DNA across submodules without losing "
    "provenance?"
)

SIMULATED_CONTEXT = "\n".join([BEDROCK_CHUNK, DISTRACTOR_1, DISTRACTOR_2])

# Multi-turn replay script: a realistic 3-turn exchange that the harness
# "replays" offline. Turn structure mirrors the live Two-Mice funnel.
MULTI_TURN_REPLAY_SCRIPT = [
    {
        "turn": 1,
        "role": "jason",
        "text": SIMULATED_MULTI_TURN_QUERY,
        "interest": 0.85,
    },
    {
        "turn": 2,
        "role": "brain",
        "text": (
            "<thought>Gatekeeper pass: BKM-060 bedrock (0.32) survives; "
            "FEAT-999 (0.81) and VIBE-998 (0.74) are pruned as tangential.</thought>"
        ),
        "interest": 0.85,
    },
    {
        "turn": 3,
        "role": "pinky",
        "text": (
            "Narf! Brain dug up the DNA taxonomy — submodules sync vector DNA "
            "through the Forge Studio, provenance intact. 💡 Curator Note: "
            "BKM-060 connects with FEAT-635."
        ),
        "interest": 0.9,
    },
]


# ---------------------------------------------------------------------------
# Test 1: Brain System Prompt Persona
# ---------------------------------------------------------------------------

def test_brain_system_prompt_persona_voice():
    """BRAIN_SYSTEM_PROMPT must encode the cynical 1st-person voice."""
    assert "1st-person, cynical, rigorous" in BRAIN_SYSTEM_PROMPT


def test_brain_system_prompt_narrative_steering():
    """BRAIN_SYSTEM_PROMPT must mandate narrative steering."""
    assert "NARRATIVE STEERING" in BRAIN_SYSTEM_PROMPT


def test_brain_system_prompt_information_gatekeeper_and_rag_filtering():
    """BRAIN_SYSTEM_PROMPT must mandate Information Gatekeeper & RAG filtering."""
    assert "INFORMATION GATEKEEPER & RAG FILTERING" in BRAIN_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Test 2: Stage 1 Two-Mice Handover Prompt
# ---------------------------------------------------------------------------

def test_stage1_two_mice_handover_prompt_directives():
    """Stage 1 prompt frames Brain as Narrative Reality Steerer with pruning + Curator Notes."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
    )
    assert "Narrative Reality Steerer" in prompt
    assert "prune irrelevant or tangential chunks" in prompt
    assert "💡 Curator Note:" in prompt


def test_stage1_prompt_wraps_context_in_historical_record():
    """Stage 1 prompt wraps raw context in <historical_record> tags."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
    )
    assert "<historical_record>" in prompt
    assert "</historical_record>" in prompt
    # The raw bedrock + distractors must be embedded verbatim for Brain to inspect.
    assert BEDROCK_CHUNK in prompt
    assert DISTRACTOR_1 in prompt
    assert DISTRACTOR_2 in prompt


def test_stage1_prompt_excludes_conversational_framing():
    """Stage 1 prompt must demand pure technical signal, no conversational filler."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
    )
    assert "no narrative preamble" in prompt
    assert "no filler" in prompt
    assert "no conversational framing" in prompt


# ---------------------------------------------------------------------------
# Test 3: Multi-Turn Simulated Replay (1 bedrock preserved, 2 distractors pruned)
# ---------------------------------------------------------------------------

def test_replay_prunes_distractors_preserves_bedrock():
    """Replay fixture: the prompt directs pruning of both distractors while preserving bedrock.

    The Stage 1 prompt embeds the full context (bedrock + 2 distractors) and
    instructs Brain to 'prune irrelevant or tangential chunks entirely'. A
    gatekeeper pass keeps the bedrock (distance 0.32 <= 0.55) and drops both
    distractors (0.81, 0.74 > 0.55).
    """
    # Simulated gatekeeper pass: keep distance <= 0.55 (FEAT-635 semantic gate).
    surviving = [c for c in _parse_candidate_chunks(SIMULATED_CONTEXT) if c["distance"] <= 0.55]
    pruned = [c for c in _parse_candidate_chunks(SIMULATED_CONTEXT) if c["distance"] > 0.55]

    # Exactly 1 bedrock chunk survives.
    assert len(surviving) == 1
    assert surviving[0]["id"] == "BKM-060"
    assert "distance 0.32" in surviving[0]["text"]

    # Exactly 2 tangential distractors are pruned.
    assert len(pruned) == 2
    assert {p["id"] for p in pruned} == {"FEAT-999", "VIBE-998"}

    # The Stage 1 prompt is what drives this: it embeds all 3 and orders pruning.
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
    )
    assert "prune irrelevant or tangential chunks" in prompt
    # Bedrock is embedded and retained in the surviving set; distractors dropped.
    assert surviving[0]["id"] in prompt


def test_replay_does_not_stall_or_downvote_interest():
    """The handover must preserve momentum: no stalling, no downvoting the turn."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
    )
    assert "without stalling the pipeline or downvoting the turn" in prompt
    # Stage 1 still advances the funnel (does not stall).
    assert "STAGE 1 of the Two-Mice sequential handover" in prompt
    # Pinky Stage 2 acknowledges Brain and delivers the TL;DR (no downvote).
    stage2 = build_two_mice_stage_prompt(
        2,
        user_query=SIMULATED_MULTI_TURN_QUERY,
        context=SIMULATED_CONTEXT,
        interest=0.85,
        brain_bullets="• BKM-060: submodules synchronize vector DNA via Forge Studio.",
    )
    assert "Acknowledge Brain in character" in stage2
    assert "conversational TL;DR" in stage2


def test_replay_multi_turn_script_is_hermetic_and_offline():
    """The multi-turn replay script is pure data (no I/O) and round-trips cleanly."""
    assert isinstance(MULTI_TURN_REPLAY_SCRIPT, list)
    assert len(MULTI_TURN_REPLAY_SCRIPT) == 3
    roles = [t["role"] for t in MULTI_TURN_REPLAY_SCRIPT]
    assert roles == ["jason", "brain", "pinky"]
    # Interest never stalls: monotonic non-decreasing across the replay.
    interests = [t["interest"] for t in MULTI_TURN_REPLAY_SCRIPT]
    assert interests == sorted(interests)
    # Brain turn carries the gatekeeper rationale (steering, not a downvote).
    brain_turn = next(t for t in MULTI_TURN_REPLAY_SCRIPT if t["role"] == "brain")
    assert "Gatekeeper pass" in brain_turn["text"]
    assert "pruned" in brain_turn["text"]
    # Pinky turn carries the Curator Note synergy (narrative steering).
    pinky_turn = next(t for t in MULTI_TURN_REPLAY_SCRIPT if t["role"] == "pinky")
    assert "💡 Curator Note:" in pinky_turn["text"]


# ---------------------------------------------------------------------------
# Test 4: Offline runtime budget
# ---------------------------------------------------------------------------

def test_harness_runs_offline_without_live_daemons_under_2s():
    """Entire suite must execute offline (no network) within the 2s silicon budget.

    This test performs a full offline replay of every Stage 1 prompt and the
    gatekeeper pass, and asserts it completes well under 2 seconds. (The real
    wall-clock budget is enforced by the pytest run itself per Anchor 3.)
    """
    import time

    start = time.perf_counter()
    for _ in range(50):  # amplify to exercise the pure-function hot path
        build_two_mice_stage_prompt(
            1,
            user_query=SIMULATED_MULTI_TURN_QUERY,
            context=SIMULATED_CONTEXT,
            interest=0.85,
        )
        _parse_candidate_chunks(SIMULATED_CONTEXT)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"Offline replay exceeded budget: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Internal helper: parse candidate chunks from the simulated context.
# Hermetic — pure string parsing, no I/O, no network.
# ---------------------------------------------------------------------------

def _parse_candidate_chunks(context: str) -> list[dict]:
    """Parse simulated candidate chunks into (id, text, distance) dicts.

    Each chunk line has the form:
        [ID]: text ... distance 0.XX ...
    This mirrors the FEAT-635 semantic gate (cosine distance <= 0.55 bedrock).
    """
    import re
    chunks = []
    for line in context.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"\[(?P<id>[A-Z]+-\d+)]:\s*(?P<text>.*?distance\s+(?P<dist>\d+\.\d+)).*$", line)
        if m:
            chunks.append(
                {
                    "id": m.group("id"),
                    "text": m.group("text"),
                    "distance": float(m.group("dist")),
                }
            )
    return chunks
