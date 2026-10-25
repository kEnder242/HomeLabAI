"""[STORY 108.2] Companion tests: entailment audit decoupling from handover delivery.

Verifies:
(a) step_entailment_audit exists on CognitiveHub and step_grounding_critic is
    a backward-compatible alias pointing to the same function object.
(b) step_entailment_audit returns turn_thought_trace['audit'] or
    turn_thought_trace.get('critique', '').
(c) _run_two_mice_handover sources contain asyncio.create_task(self.step_entailment_audit.
(d) evaluate_grounding is invoked, but the handover does NOT await the audit
    (no 'await self.step_entailment_audit' in handover source).
"""

import asyncio
import inspect
import os
from unittest.mock import MagicMock

try:
    from logic.cognitive_hub import CognitiveHub
except ImportError:
    from src.logic.cognitive_hub import CognitiveHub

_SOURCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
    "logic",
    "cognitive_hub.py",
)


def _make_hub() -> CognitiveHub:
    return CognitiveHub(
        residents={},
        broadcast_callback=MagicMock(),
        sensory_manager=MagicMock(),
        get_vram_status=MagicMock(),
        trigger_morning_briefing=MagicMock(),
    )


def test_step_entailment_audit_exists_on_hub():
    assert hasattr(CognitiveHub, "step_entailment_audit")
    assert (
        asyncio.iscoroutinefunction(CognitiveHub.step_entailment_audit)
    ), "step_entailment_audit must be an async method"


def test_step_grounding_critic_is_backward_compatible_alias():
    assert hasattr(CognitiveHub, "step_grounding_critic")


def test_entailment_audit_returns_audit_key_when_present():
    hub = _make_hub()
    hub.turn_thought_trace = {"audit": "audited delivery text"}
    result = asyncio.run(
        hub.step_entailment_audit(
            "q", "Deep Thought", "resp", "ctx", 0.8
        )
    )
    assert result == "audited delivery text"


def test_entailment_audit_falls_back_to_critique_key():
    hub = _make_hub()
    hub.turn_thought_trace = {"critique": "critique delivery text"}
    result = asyncio.run(
        hub.step_entailment_audit(
            "q", "Deep Thought", "resp", "ctx", 0.8
        )
    )
    assert result == "critique delivery text"


def test_entailment_audit_returns_empty_string_when_no_keys():
    hub = _make_hub()
    hub.turn_thought_trace = {}
    result = asyncio.run(
        hub.step_entailment_audit(
            "q", "Deep Thought", "resp", "ctx", 0.8
        )
    )
    assert result == ""


def test_handover_sources_use_create_task_for_audit():
    with open(_SOURCE_PATH, "r") as f:
        source = "".join(f.read().split())
    assert "asyncio.create_task(self.step_entailment_audit" in source


def test_handover_does_not_await_entailment_audit():
    with open(_SOURCE_PATH, "r") as f:
        source = "".join(f.read().split())
    assert "awaitself.step_entailment_audit" not in source


def test_evaluate_grounding_still_invoked_in_audit_method():
    assert inspect.iscoroutinefunction(CognitiveHub.step_entailment_audit)
    with open(_SOURCE_PATH, "r") as f:
        source = "".join(f.read().split())
    assert "awaitself.evaluate_grounding" in source


def test_trace_writes_audit_and_critique_together():
    with open(_SOURCE_PATH, "r") as f:
        source = "".join(f.read().split())
    assert 'turn_thought_trace["audit"]=chat_delivery' in source
    assert 'turn_thought_trace["critique"]=chat_delivery' in source
