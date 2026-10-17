"""[STORY 105.10] Post-Waterfall Learning Target Queueing tests.

Hermetic unit tests for queue_post_waterfall_learning_target:
atomic flock-protected append + dedup against queue.json.
"""

import json
import os

import pytest

from logic.cognitive_hub import (
    POST_WATERFALL_QUEUE_PATH,
    queue_post_waterfall_learning_target,
)


@pytest.fixture
def queue_env(tmp_path, monkeypatch):
    """Redirect the queue file into a temp dir so tests never touch real data."""
    queue_path = tmp_path / "queue.json"
    monkeypatch.setattr(
        "logic.cognitive_hub.POST_WATERFALL_QUEUE_PATH", str(queue_path)
    )
    return queue_path


def _load(queue_path):
    with open(queue_path, "r") as f:
        return json.load(f)


def test_append_creates_queue_with_expected_schema(queue_env):
    assert queue_post_waterfall_learning_target("What is PECI?", ["PECI"]) is True
    data = _load(queue_env)
    assert isinstance(data, list) and len(data) == 1
    entry = data[0]
    assert entry["query"] == "What is PECI?"
    assert entry["entities"] == ["PECI"]
    assert entry["status"] == "pending"
    assert entry["key"] and isinstance(entry["queued_at"], int)


def test_duplicate_is_deduped(queue_env):
    assert queue_post_waterfall_learning_target("What is RAPL?", ["RAPL"]) is True
    assert queue_post_waterfall_learning_target("What is RAPL?", ["RAPL"]) is False
    # Exact-match dedup: whitespace-padded variant is a distinct query by design.
    assert queue_post_waterfall_learning_target("  what is rapl  ", ["RAPL"]) is True
    assert len(_load(queue_env)) == 2


def test_entity_order_and_case_do_not_affect_dedup(queue_env):
    assert queue_post_waterfall_learning_target("q", ["PECI", "RAPL"]) is True
    assert queue_post_waterfall_learning_target("q", ["rapl", "peci"]) is False
    assert len(_load(queue_env)) == 1


def test_distinct_queries_both_queued(queue_env):
    assert queue_post_waterfall_learning_target("A?", ["PECI"]) is True
    assert queue_post_waterfall_learning_target("B?", ["PECI"]) is True
    assert len(_load(queue_env)) == 2


def test_no_torn_file_left_behind(queue_env):
    queue_post_waterfall_learning_target("Q1", ["X"])
    leftovers = [p for p in os.listdir(queue_env.parent) if p.endswith(".tmp")]
    assert leftovers == []


def test_handover_scarce_synthesis_invokes_queue(monkeypatch):
    """Integration: _run_two_mice_handover queues on scarce DT synthesis."""
    from unittest.mock import AsyncMock, MagicMock

    from logic.cognitive_hub import CognitiveHub

    calls = []
    monkeypatch.setattr(
        "logic.cognitive_hub.queue_post_waterfall_learning_target",
        lambda q, entities=None: calls.append((q, entities)) or True,
    )
    hub = MagicMock(spec=CognitiveHub)
    hub.residents = {"brain": object(), "pinky": object()}
    hub.current_interest = 0.9
    hub.current_vibe = "TECHNICAL"
    hub.turn_thought_trace = {}
    hub._last_pinky_greeting = ""
    hub.step_brain_gatekeeper = AsyncMock(return_value="grounding text")
    hub.step_deep_thought = AsyncMock(return_value="Evidence is scarce.")
    hub.step_pinky_voice = AsyncMock(return_value=None)
    hub.step_grounding_critic = AsyncMock(return_value=None)

    import asyncio

    asyncio.run(
        CognitiveHub._run_two_mice_handover(
            hub, "What is PECI?", focus_context="", interest=0.9,
            shutdown_event=None, request_id="t",
        )
    )
    # Query contains PECI, so the handover extracts entities=['PECI'] and queues them.
    assert ("What is PECI?", ["PECI"]) in calls
