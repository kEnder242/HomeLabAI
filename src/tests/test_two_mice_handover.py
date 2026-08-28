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
    CognitiveHub,
    TWO_MICE_BRAIN_SOURCE,
    TWO_MICE_BRAIN_CHANNEL,
    TWO_MICE_BRAIN_CONSOLE,
    TWO_MICE_PINKY_SOURCE,
    TWO_MICE_PINKY_CHANNEL,
    TWO_MICE_PINKY_CONSOLE,
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
    # Pillar 2 [FEAT-403]: Interest loop awareness.
    assert "INTEREST LOOP AWARENESS" in prompt
    assert "Distillation Funnel active" in prompt
    # Pillar 3 [FEAT-236]: Stage numbering.
    assert "STAGE 1" in prompt
    assert "STAGE_1_INSTRUCTIONS" in prompt
    # Grounding: user query + historical record wrapped in tags.
    assert "ESB2 server" in prompt
    assert "<historical_record>" in prompt and "</historical_record>" in prompt
    assert "3-4 dense" in prompt and "pure technical signal" in prompt


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
    prompt = build_two_mice_stage_prompt(2, user_query="ESB2?", interest=0.9, brain_bullets="")
    assert "STAGE_2_INSTRUCTIONS" in prompt
    assert "Brain returned no extraction" in prompt


def test_stage_prompt_rejects_invalid_stage():
    """Only stages 1 and 2 exist in the funnel."""
    try:
        build_two_mice_stage_prompt(3, user_query="x")
    except ValueError:
        return
    raise AssertionError("Expected ValueError for stage=3")


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
        source=TWO_MICE_BRAIN_SOURCE, channel=TWO_MICE_BRAIN_CHANNEL,
        console=TWO_MICE_BRAIN_CONSOLE, token="• ESB2", final=False, request_id="r1",
    )
    pinky_packet = build_two_mice_stream_packet(
        source=TWO_MICE_PINKY_SOURCE, channel=TWO_MICE_PINKY_CHANNEL,
        console=TWO_MICE_PINKY_CONSOLE, token="Narf!", final=True, request_id="r1",
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
    result = parse_critic_payload(json.dumps({
        "retort": "Narf! The firmware logs were under the ESB2.",
        "critique_suggestions": ["add the MSR test"],
        "score": 4,
        "reasoning": "mostly grounded",
    }))
    assert isinstance(result, CriticResult)
    assert result.retort == "Narf! The firmware logs were under the ESB2."
    assert result.cartoon_retort == result.retort
    assert "missing" not in result.retort.lower()
    assert result.score == 4


def test_critic_parses_cartoon_retort_key():
    """'cartoon_retort' remains fully supported."""
    result = parse_critic_payload(json.dumps({
        "cartoon_retort": "Poit! Right console, right answer.",
        "critique_suggestions": [],
    }))
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
            self.hub.session_buffers[buf_key] += self.text[i:i + chunk_size]
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

    # Order: Brain's Stage 1 call strictly precedes Pinky's Stage 2 call.
    assert len(brain_node.calls) == 1 and len(pinky_node.calls) == 1
    brain_call, pinky_call = brain_node.calls[0], pinky_node.calls[0]
    assert brain_call["name"] == "think" and pinky_call["name"] == "think"

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
    assert packets[-1]["source"] == TWO_MICE_PINKY_SOURCE and packets[-1]["final"] is True

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
        ran = loop.run_until_complete(hub._run_two_mice_handover("q?", focus_context="c", request_id="tm2"))
    finally:
        loop.close()
    assert ran is False

    # Restore; low interest gates the funnel dormant.
    hub.residents["pinky"] = _FakeResident(hub, "pinky", PINKY_TLDR_TEXT)
    hub.current_interest = 0.3
    loop = asyncio.new_event_loop()
    try:
        ran = loop.run_until_complete(hub._run_two_mice_handover("q?", focus_context="c", request_id="tm3"))
    finally:
        loop.close()
    assert ran is False
    assert hub.residents["brain"].calls == []  # funnel did not run
    assert hub.current_interest == 0.3  # gate value unchanged below threshold


def test_module_level_alias_is_bound():
    """The module-level alias exposes the handover entry point."""
    from logic.cognitive_hub import run_two_mice_handover

    assert callable(run_two_mice_handover)
    assert run_two_mice_handover is CognitiveHub._run_two_mice_handover
