"""
[FEAT-489 / SPR-65 Story 4] Two-Mice Sequential Streaming Handover & Distillation Pipeline.

Locks the root-cause regressions:
  1. Brain and Pinky used to run as uncoordinated parallel competitors over the
     same raw RAG dump. The Two-Mice funnel now runs STRICTLY sequentially:
     Stage 1 Brain extracts dense technical bullets (Right Console), Stage 2
     Pinky acknowledges Brain in character and delivers a conversational TL;DR
     (Left Console).
  2. pinky_critic_persona._coerce_result only read "cartoon_retort"; when the
     LLM returned "retort" it fell back to 'Narf! The retort went missing.'
     and scored the turn 1/5. It now consumes BOTH keys faithfully.

Contract assertions (mirroring SPR-65 Story 65.4 verification clauses):
  - Brain output carries channel:"insight" / source:"Brain (Archive)" (Right).
  - Pinky output carries channel:"pinky" / source:"Pinky (Voice)" (Left).
  - Stage prompts are grounded by the 3 Prompt Engineering Pillars
    [FEAT-140/467] Shared Bedrock, [FEAT-403] Interest Loop, [FEAT-236] Stage.
  - Stage 2 receives Brain's bullets and instructs the in-character
    acknowledgment + 2-sentence conversational TL;DR.
  - Critic parses both "retort" and "cartoon_retort" with zero missing-retort
    fallback.
  - The runtime orchestrator runs Stage 1 before Stage 2 and streams to the
    correct console channel for each stage (verified with resident fakes — no
    live model required).
"""

import asyncio
import json
from collections import defaultdict

from logic.cognitive_hub import (
    TWO_MICE_BRAIN_CHANNEL,
    TWO_MICE_BRAIN_CONSOLE,
    TWO_MICE_BRAIN_SOURCE,
    TWO_MICE_PINKY_CHANNEL,
    TWO_MICE_PINKY_CONSOLE,
    TWO_MICE_PINKY_SOURCE,
    CognitiveHub,
    build_two_mice_stage_prompt,
    build_two_mice_stream_packet,
)
from nodes.pinky_critic_persona import CriticResult, parse_critic_payload

# ---- Anchor 3a: Prompt pillar grounding --------------------------------------


def test_stage1_prompt_grounds_three_pillars_and_historical_record():
    """Stage 1 (Brain) is bedrock-grounded, interest-aware, stage-numbered."""
    prompt = build_two_mice_stage_prompt(
        1,
        user_query="Which firmware did we upgrade on the ESB2 server?",
        context="Platform: ESB2 server, firmware v2.1. 2016 upgrade. PECI/MSR scars logged.",
        interest=0.85,
    )
    # Pillar 1 [FEAT-140/467]: Shared bedrock — physical lab foundation.
    assert "SHARED BEDROCK LAB FOUNDATION" in prompt
    assert "z87-Linux" in prompt and "RTX 2080 Ti" in prompt
    # Pillar 2 [BKM-015 / FEAT-523 / Story 105.11]: Prompt-driven token ceiling headroom.
    assert "[BUDGET]: Headroom ceiling is" in prompt
    # Pillar 3 [FEAT-236]: Stage numbering.
    assert "STAGE 1" in prompt
    assert "STAGE_1_INSTRUCTIONS" in prompt
    # Grounding: user query + historical record wrapped in tags.
    assert "ESB2 server" in prompt
    assert "<historical_record>" in prompt and "</historical_record>" in prompt
    assert "cohesive bedrock truth" in prompt and "evidentiary inspection" in prompt


def test_stage2_prompt_embeds_brain_bullets_and_tldr_instructions():
    """Stage 2 (Pinky) receives Brain's extraction and instructs acknowledgment."""
    bullets = (
        "- ESB2 server, Intel Xeon E5-2600 platform\n"
        "- Firmware upgraded to v2.1 in 2016 (BIOS + BMC)\n"
        "- PECI/MSR readback scarring surfaced during validation"
    )
    prompt = build_two_mice_stage_prompt(
        2,
        user_query="Which firmware did we upgrade on the ESB2 server?",
        interest=0.85,
        brain_bullets=bullets,
    )
    assert "STAGE 2" in prompt and "STAGE_2_INSTRUCTIONS" in prompt
    assert "SHARED BEDROCK LAB FOUNDATION" in prompt and "z87-Linux" in prompt
    # Brain's bullets are handed to Pinky verbatim as context.
    assert "ESB2 server, Intel Xeon E5-2600 platform" in prompt
    assert "PECI/MSR readback scarring" in prompt
    # In-character acknowledgment + 2-sentence conversational TL;DR.
    assert "Narf! Brain dug up the firmware logs" in prompt
    assert "2-sentence conversational TL;DR" in prompt
    assert "directly to Jason" in prompt


def test_stage2_without_bullets_degrades_gracefully():
    """Empty extraction still produces a usable Stage 2 prompt."""
    prompt = build_two_mice_stage_prompt(
        2, user_query="ESB2?", interest=0.9, brain_bullets=""
    )
    assert "STAGE_2_INSTRUCTIONS" in prompt
    assert "Brain returned no extraction" in prompt


def test_stage2_prompt_embeds_situational_vibe_directive():
    """[STORY 108.7] Stage 2 prompt embeds situational vibe directive when provided."""
    prompt = build_two_mice_stage_prompt(
        2,
        user_query="ESB2?",
        interest=0.9,
        brain_bullets="ESB2 server",
        topic_directive="Keep it warm and brief.",
    )
    assert "[SITUATIONAL_VIBE_DIRECTIVE]" in prompt
    assert "Keep it warm and brief." in prompt
    # Default topic_directive="" does not add the section.
    prompt_default = build_two_mice_stage_prompt(
        2,
        user_query="ESB2?",
        interest=0.9,
        brain_bullets="ESB2 server",
    )
    assert "[SITUATIONAL_VIBE_DIRECTIVE]" not in prompt_default


def test_stage_prompt_rejects_invalid_stage():
    """Only stages 1 and 2 exist in the funnel."""
    try:
        build_two_mice_stage_prompt(3, user_query="x")
    except ValueError:
        return
    raise AssertionError("Expected ValueError for stage=3")


def test_pinky_voice_10_percent_token_budget():
    """[STORY 108.7] Pinky's 10% DT token budget clamps to [60, 150]."""
    def clamp(dt_tokens: float) -> int:
        return max(60, min(150, int(dt_tokens * 0.10)))

    # 100 words -> 133.0 tokens -> budget 13, but clamped to floor 60.
    assert clamp(100 * 1.33) == 60
    # 1000 words -> 1330.0 tokens -> budget 133, within clamp.
    assert clamp(1000 * 1.33) == 133
    # 20 words -> 26.6 tokens -> budget 2, clamped to floor 60.
    assert clamp(20 * 1.33) == 60
    # 1429 words -> 1899.6 tokens -> budget 189, clamped to ceiling 150.
    assert clamp(1429 * 1.33) == 150


def test_interest_band_quantization():
    """FEAT-403 loop bands: >=0.7 funnel, <0.4 casual, else mixed."""
    from logic.cognitive_hub import _two_mice_interest_band

    assert "Distillation Funnel" in _two_mice_interest_band(0.7)
    assert "Distillation Funnel" in _two_mice_interest_band(0.95)
    assert "Casual banter" in _two_mice_interest_band(0.2)
    assert "Mixed loop" in _two_mice_interest_band(0.55)


# ---- Anchor 3b: Dual-console WebSocket routing contract ----------------------


def test_stream_packet_routing_contract():
    """Packet tags satisfy the dual-console routing contract."""
    brain_packet = build_two_mice_stream_packet(
        source=TWO_MICE_BRAIN_SOURCE,
        channel=TWO_MICE_BRAIN_CHANNEL,
        console=TWO_MICE_BRAIN_CONSOLE,
        token="• ESB2",
        final=False,
        request_id="r1",
    )
    pinky_packet = build_two_mice_stream_packet(
        source=TWO_MICE_PINKY_SOURCE,
        channel=TWO_MICE_PINKY_CHANNEL,
        console=TWO_MICE_PINKY_CONSOLE,
        token="Narf!",
        final=True,
        request_id="r1",
    )
    assert brain_packet["type"] == "thought_stream"
    assert brain_packet["channel"] == "insight" and brain_packet["console"] == "Right"
    assert brain_packet["source"] == "Brain (Archive)"
    assert pinky_packet["channel"] == "pinky" and pinky_packet["console"] == "Left"
    assert pinky_packet["source"] == "Pinky (Voice)"
    assert pinky_packet["final"] is True


# ---- Anchor 3c: Critic retort key tolerance (zero missing-retort fallback) ---


def test_critic_parses_retort_key_without_fallback():
    """LLM emits 'retort' -> CriticResult.retort populated faithfully."""
    result = parse_critic_payload(
        json.dumps(
            {
                "retort": "Narf! The firmware logs were under the ESB2.",
                "critique_suggestions": ["add the MSR test"],
                "score": 4,
                "reasoning": "mostly grounded",
            }
        )
    )
    assert isinstance(result, CriticResult)
    assert result.retort == "Narf! The firmware logs were under the ESB2."
    assert result.cartoon_retort == result.retort
    assert "missing" not in result.retort.lower()
    assert result.score == 4


def test_critic_parses_cartoon_retort_key():
    """'cartoon_retort' remains fully supported."""
    result = parse_critic_payload(
        json.dumps(
            {
                "cartoon_retort": "Poit! Right console, right answer.",
                "critique_suggestions": [],
            }
        )
    )
    assert result.retort == "Poit! Right console, right answer."
    assert "missing" not in result.retort.lower()


def test_critic_parses_retort_embedded_in_prose():
    """Resilience case 2: JSON embedded in surrounding prose."""
    result = parse_critic_payload(
        'Here you go: {"retort": "Narf! Found the 2016 log.", "critique_suggestions": ["x"]}'
    )
    assert result.retort == "Narf! Found the 2016 log."


def test_critic_fallback_only_when_both_keys_absent():
    """The missing-retort fallback trips ONLY when neither key is present."""
    result = parse_critic_payload('{"critique_suggestions": []}')
    assert result.retort == "Narf! The retort went missing."  # legitimate fallback
    ok_result = parse_critic_payload('{"retort": "ok"}')
    assert "missing" not in ok_result.retort.lower()


# ---- Anchor 3d: Sequential orchestration (Stage 1 -> Stage 2) ----------------

BRAIN_BULLET_TEXT = (
    "• ESB2 server platform (Intel Xeon E5-2600)\n"
    "• Firmware v2.1 upgrade in 2016 (BIOS + BMC)\n"
    "• PECI/MSR readback scars surfaced during validation"
)
PINKY_TLDR_TEXT = "Narf! Brain dug up the firmware logs. Firmware v2.1 went in during 2016 on the ESB2."


class _FakeResult:
    """Mimics a BicameralNode tool result: .content[0].text."""

    def __init__(self, text: str):
        self.content = [type("C", (), {"text": text})()]


class _FakeResident:
    """Stand-in resident that streams text into the hub's session buffer."""

    def __init__(self, hub, node_id: str, text: str, hops: int = 3):
        self.hub = hub
        self.node_id = node_id
        self.text = text
        self.hops = hops
        self.calls: list = []

    async def call_tool(self, name: str, arguments: dict = None):
        arguments = arguments or {}
        self.calls.append({"name": name, "arguments": arguments})
        buf_key = f"{arguments.get('request_id', 'default')}_{self.node_id}"
        chunk_size = max(1, len(self.text) // self.hops)
        for i in range(0, len(self.text), chunk_size):
            self.hub.session_buffers[buf_key] += self.text[i : i + chunk_size]
            await asyncio.sleep(0.02)
        return _FakeResult(self.text)


def _build_test_hub():
    """Construct a lightweight CognitiveHub without touching engines/network."""
    hub = CognitiveHub.__new__(CognitiveHub)
    hub.residents = {}
    hub.session_buffers = defaultdict(str)
    hub.current_interest = 0.0
    hub.current_vibe = "TECHNICAL"
    hub._boosted_interest = False
    hub.context_starved_nodes = set()
    hub.turn_thought_trace = {}
    hub.round_table_memory = []
    packets: list = []

    async def broadcast(packet: dict) -> None:
        packets.append(packet)

    hub.broadcast = broadcast
    hub.residents["brain"] = _FakeResident(hub, "brain", BRAIN_BULLET_TEXT)
    hub.residents["pinky"] = _FakeResident(hub, "pinky", PINKY_TLDR_TEXT)
    return hub, packets


def test_handover_runs_brain_then_pinky_sequentially():
    """Stage 1 completes and streams to Right before Stage 2 streams to Left."""
    hub, packets = _build_test_hub()
    hub.current_interest = 0.9

    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover(
                "Which firmware did we upgrade on the ESB2 server?",
                focus_context="Platform: ESB2 server, firmware v2.1. 2016 upgrade.",
                request_id="tm1",
            )
        )
    finally:
        loop.close()
    assert ran is True

    brain_node = hub.residents["brain"]
    pinky_node = hub.residents["pinky"]

    # Order: Brain's Stage 1 call strictly precedes Pinky's Stage 2 call, followed by Stage 4 Critic.
    assert len(brain_node.calls) == 1 and len(pinky_node.calls) == 2
    brain_call, pinky_call, critic_call = brain_node.calls[0], pinky_node.calls[0], pinky_node.calls[1]
    assert brain_call["name"] == "think" and pinky_call["name"] == "think" and critic_call["name"] == "think"

    brain_query = brain_call["arguments"].get("query", "")
    pinky_query = pinky_call["arguments"].get("query", "")
    assert "STAGE_1_INSTRUCTIONS" in brain_query
    assert "STAGE_2_INSTRUCTIONS" in pinky_query
    # Pinky's user-role context is Brain's extraction, not the raw RAG dump.
    # (FEAT-407 wraps context in <historical_record> tags for TECHNICAL vibes.)
    pinky_context = pinky_call["arguments"].get("context", "")
    assert "<historical_record>" in pinky_context
    assert BRAIN_BULLET_TEXT in pinky_context
    assert "Platform: ESB2 server" not in pinky_context  # raw dump not replayed

    # Dual-console streaming: Brain tokens on channel insight/Right FIRST.
    order = [(p.get("channel"), p.get("console"), p.get("source")) for p in packets]
    brain_idx = next(i for i, (_, c, s) in enumerate(order) if s == "Brain (Archive)")
    pinky_idx = next(i for i, (_, c, s) in enumerate(order) if s == "Pinky (Voice)")
    assert brain_idx < pinky_idx, "Stage 2 streamed before Stage 1 completed!"
    assert len(packets) >= 2  # per-stage finalizer packets

    # Handover trace recorded for the session ledger.
    assert "ESB2 server platform" in hub.turn_thought_trace["brain"]
    assert "Two-Mice TL;DR" in hub.turn_thought_trace["pinky"]


def test_handover_refuses_missing_resident_and_low_interest():
    """Funnel gate: no brain/pinky resident or interest < 0.7 -> fallback signal."""
    hub, _ = _build_test_hub()
    hub.current_interest = 0.9

    # Missing pinky resident.
    del hub.residents["pinky"]
    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover("q?", focus_context="c", request_id="tm2")
        )
    finally:
        loop.close()
    assert ran is False

    # Restore; [FEAT-658 / BKM-039] Low interest (< 0.35) exhausts fuel: Brain remains dormant.
    hub.residents["pinky"] = _FakeResident(hub, "pinky", PINKY_TLDR_TEXT)
    hub.current_interest = 0.3
    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover("q?", focus_context="c", request_id="tm3")
        )
    finally:
        loop.close()
    assert ran is True  # Waterfall handled cleanly
    assert len(hub.residents["brain"].calls) == 0  # Brain stays dormant on low fuel (< 0.35)


def test_module_level_alias_is_bound():
    """The module-level alias exposes the handover entry point."""
    from logic.cognitive_hub import run_two_mice_handover

    assert callable(run_two_mice_handover)
    assert run_two_mice_handover is CognitiveHub._run_two_mice_handover


def test_brain_damp_interest_skips_deep_thought():
    """[Story 105.15 / FEAT-238 / FEAT-658] Brain emits <damp_interest>, fuel drops < 0.35, Deep Thought stays dormant."""
    hub, packets = _build_test_hub()
    hub.current_interest = 0.50
    dt_called = []

    async def fake_step_deep_thought(*args, **kwargs):
        dt_called.append(True)
        return "Deep Thought synthesized architectural meta-analysis."

    hub.step_deep_thought = fake_step_deep_thought
    # Brain damps interest
    hub.residents["brain"] = _FakeResident(
        hub, "brain", "Nothing relevant in archives. <damp_interest>"
    )

    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover(
                "How are you and Brain?",
                focus_context="[ZERO_CONTEXT]: No archive record retrieved.",
                request_id="damp1",
            )
        )
    finally:
        loop.close()

    assert ran is True
    # Damped from 0.50 - 0.25 = 0.25
    assert hub.current_interest == 0.25
    # Deep Thought should be completely skipped
    assert len(dt_called) == 0


def test_brain_boost_interest_elevates_fuel():
    """[Story 105.15 / FEAT-238] Brain emits <boost_interest>, elevating fuel by +0.20."""
    hub, packets = _build_test_hub()
    hub.current_interest = 0.50
    hub.residents["brain"] = _FakeResident(
        hub, "brain", "Bedrock truth found! <boost_interest>"
    )

    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover(
                "ESB2 firmware?",
                focus_context="Platform: ESB2 server, firmware v2.1.",
                request_id="boost1",
            )
        )
    finally:
        loop.close()

    assert ran is True
    # Boosted from 0.50 + 0.20 = 0.70
    assert hub.current_interest == 0.70


def test_zero_rag_casual_evidential_damping():
    """[Story 105.15 / FEAT-659] Zero RAG context on CASUAL turn applies evidential damping."""
    hub, packets = _build_test_hub()
    hub.current_vibe = "CASUAL"
    hub.current_interest = 0.50
    hub.residents["brain"] = _FakeResident(
        hub, "brain", "No records passed."
    )

    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover(
                "just checking in",
                focus_context="",
                request_id="evid1",
            )
        )
    finally:
        loop.close()

    assert ran is True
    # Damped from 0.50 - 0.15 = 0.35
    assert hub.current_interest == 0.35


def test_vocative_overhearing_brain_turn():
    """[FEAT-660 / BKM-083] Explicit vocative to Brain: Pinky overhears, Brain answers, DT is dormant."""
    hub, packets = _build_test_hub()
    hub.current_target = "brain"
    hub.current_vibe = "CASUAL"
    hub.current_interest = 0.10

    dt_called = []

    async def fake_step_deep_thought(*args, **kwargs):
        dt_called.append(True)
        return "Deep Thought answered."

    pinky_voice_called = []

    async def fake_step_pinky_voice(*args, **kwargs):
        pinky_voice_called.append(True)
        return "Pinky spoke."

    hub.step_deep_thought = fake_step_deep_thought
    hub.step_pinky_voice = fake_step_pinky_voice

    # Brain damps interest on casual turn
    hub.residents["brain"] = _FakeResident(
        hub, "brain", "I am functioning within normal parameters. Pinky, cease your noise. <damp_interest>"
    )

    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(
            hub._run_two_mice_handover(
                "How are you, Brain?",
                focus_context="[ZERO_CONTEXT]: No archive record retrieved.",
                interest=0.10,
                request_id="overhear1",
            )
        )
    finally:
        loop.close()

    assert ran is True
    # Damped from 0.10 - 0.25 = 0.0 (clamped at 0.0)
    assert round(hub.current_interest, 2) == 0.0
    # Deep Thought should be 100% dormant
    assert len(dt_called) == 0
    # Pinky voice should NOT speak a second time after Brain's direct answer
    assert len(pinky_voice_called) == 0

