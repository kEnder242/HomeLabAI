"""
[STORY 112.70] Unit test: Round table continuity vector extraction and Deep Thought hydration.
Tests for CONTINUITY_VECTOR (THREAD_CONTINUATION/TOPIC_PIVOT) extraction and UNTANGLING_DIRECTIVE injection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.logic.cognitive_hub import (
    CognitiveHub,
    extract_continuity_vector,
)


@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    pinky.list_tools = AsyncMock(return_value=MagicMock(tools=[MagicMock(name="think")]))

    brain = MagicMock()
    brain.call_tool = AsyncMock()
    brain.list_tools = AsyncMock(return_value=MagicMock(tools=[MagicMock(name="deep_think")]))

    thought = MagicMock()
    thought.call_tool = AsyncMock()
    thought.list_tools = AsyncMock(return_value=MagicMock(tools=[MagicMock(name="think")]))

    return {"pinky": pinky, "brain": brain, "thought": thought}


@pytest.fixture
def hub(mock_residents):
    broadcast = AsyncMock()
    sensory = MagicMock()
    vram_status = MagicMock(return_value={"vram": "idle"})
    trigger_morning = AsyncMock()

    hub_inst = CognitiveHub(
        residents=mock_residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=vram_status,
        trigger_morning_briefing=trigger_morning,
    )
    return hub_inst


class TestExtractContinuityVector:
    """Unit tests for the module-level continuity vector extractor."""

    def test_thread_continuation_same_topic(self):
        """When current and prior turns discuss the same domain, return THREAD_CONTINUATION."""
        query = "What about the RAM usage on that thread?"
        brain_grounding = "Memory usage is within bounds."
        trailing = "User: Explain the memory management in the probe round table."
        assert extract_continuity_vector(query, brain_grounding, trailing) == "THREAD_CONTINUATION"

    def test_topic_pivot_new_subject(self):
        """When query pivots to a new subject, return TOPIC_PIVOT."""
        query = "How do I configure OpenBMC firmware updates?"
        brain_grounding = ""
        trailing = "User: What was the last fix applied to the kernel?"
        assert extract_continuity_vector(query, brain_grounding, trailing) == "TOPIC_PIVOT"

    def test_thread_continuation_follow_up(self):
        """Follow-up query on prior topic returns THREAD_CONTINUATION."""
        query = "Can you explain that more deeply?"
        brain_grounding = ""
        trailing = "User: What is the current state of the probe round table?"
        assert extract_continuity_vector(query, brain_grounding, trailing) == "THREAD_CONTINUATION"

    def test_topic_pivot_different_domain(self):
        """Different domains indicate a topic pivot."""
        query = "Tell me about the GPU architecture."
        brain_grounding = ""
        trailing = "User: Explain the CPU power profiling."
        assert extract_continuity_vector(query, brain_grounding, trailing) == "TOPIC_PIVOT"

    def test_empty_trailing_text(self):
        """Empty trailing turn text defaults to THREAD_CONTINUATION."""
        assert extract_continuity_vector("Any query", "", "") == "THREAD_CONTINUATION"

    def test_continuation_with_greeting_filler(self):
        """Query with greeting fillers on same topic should still be continuation."""
        query = "Hello, can you tell me about the probe round table?"
        brain_grounding = ""
        trailing = "User: What is the current state of the probe round table?"
        assert extract_continuity_vector(query, brain_grounding, trailing) == "THREAD_CONTINUATION"


@pytest.mark.asyncio
class TestContinuityVectorInBrainGatekeeper:
    """Integration tests for continuity vector storage in step_brain_gatekeeper."""

    @pytest.mark.asyncio
    async def test_brain_gatekeeper_stores_thread_continuation(self, hub):
        """step_brain_gatekeeper stores THREAD_CONTINUATION in turn_thought_trace."""
        hub.round_table_memory.append(
            {"text": "User: What is the current state of the probe round table?", "ts": 0}
        )
        hub.current_interest = 0.8
        hub.current_vibe = "TECHNICAL"
        hub.turn_thought_trace = {}

        async def _mock_process(*args, **kwargs):
            yield "Memory usage is within bounds."

        # Patch to return the async generator
        with patch.object(hub, "_process_node_stream", return_value=_mock_process()):
            result = await hub.step_brain_gatekeeper(
                query="What about the RAM usage on that thread?",
                rag_context="context",
                interest=0.8,
                pinky_take="",
                shutdown_event=None,
                request_id="default",
            )
            assert hub.turn_thought_trace.get("continuity_vector") == "THREAD_CONTINUATION"
            assert hub.turn_thought_trace.get("brain") is not None

    @pytest.mark.asyncio
    async def test_brain_gatekeeper_stores_topic_pivot(self, hub):
        """step_brain_gatekeeper stores TOPIC_PIVOT when query diverges."""
        hub.round_table_memory.append(
            {"text": "User: What was the last fix applied to the kernel?", "ts": 0}
        )
        hub.current_interest = 0.8
        hub.current_vibe = "TECHNICAL"
        hub.turn_thought_trace = {}

        async def _mock_process(*args, **kwargs):
            yield "Kernel patch applied to x86 system."

        with patch.object(hub, "_process_node_stream", return_value=_mock_process()):
            result = await hub.step_brain_gatekeeper(
                query="How do I configure OpenBMC firmware updates?",
                rag_context="context",
                interest=0.8,
                pinky_take="",
                shutdown_event=None,
                request_id="default",
            )
            assert hub.turn_thought_trace.get("continuity_vector") == "TOPIC_PIVOT"


@pytest.mark.asyncio
class TestDeepThoughtUntanglingDirective:
    """Tests for UNTANGLING_DIRECTIVE injection in step_deep_thought."""

    @pytest.mark.asyncio
    async def test_deep_thought_adds_directive_on_topic_pivot(self, hub):
        """step_deep_thought injects UNTANGLING_DIRECTIVE when continuity_vector == TOPIC_PIVOT."""
        hub.turn_thought_trace = {}
        hub.turn_thought_trace["continuity_vector"] = "TOPIC_PIVOT"
        hub.current_interest = 0.8
        hub.current_vibe = "TECHNICAL"
        hub.round_table_memory = []

        async def _mock_process(*args, **kwargs):
            yield "[thought]Hello world[/thought]"

        # Record what was passed to _process_node_stream by patching at call time
        recorded_args = []
        async def _mock_process_w_record(*args, **kwargs):
            recorded_args.append(args)
            yield "[thought]Hello world[/thought]"

        with patch.object(hub, "_process_node_stream", side_effect=_mock_process_w_record):
            result = await hub.step_deep_thought(
                query="How do I configure OpenBMC firmware updates?",
                brain_grounding="",
                interest=0.8,
                shutdown_event=None,
                request_id="default",
            )
            # Get the last call args
            if recorded_args:
                dt_prompt = recorded_args[-1][1] if len(recorded_args[-1]) >= 2 else None
                assert dt_prompt is not None
                assert "[UNTANGLING_DIRECTIVE]" in dt_prompt
                assert "pivoted to a distinct technical subject" in dt_prompt
                assert "Do not conflate entities" in dt_prompt

    @pytest.mark.asyncio
    async def test_deep_thought_no_directive_on_thread_continuation(self, hub):
        """step_deep_thought does NOT inject directive when continuity_vector == THREAD_CONTINUATION."""
        hub.turn_thought_trace = {}
        hub.turn_thought_trace["continuity_vector"] = "THREAD_CONTINUATION"
        hub.current_interest = 0.8
        hub.current_vibe = "TECHNICAL"
        hub.round_table_memory = []

        recorded_args = []
        async def _mock_process_w_record(*args, **kwargs):
            recorded_args.append(args)
            yield "[thought]Hello world[/thought]"

        with patch.object(hub, "_process_node_stream", side_effect=_mock_process_w_record):
            result = await hub.step_deep_thought(
                query="Can you explain the memory management deeper?",
                brain_grounding="",
                interest=0.8,
                shutdown_event=None,
                request_id="default",
            )
            if recorded_args:
                dt_prompt = recorded_args[-1][1] if len(recorded_args[-1]) >= 2 else None
                if dt_prompt:
                    assert "[UNTANGLING_DIRECTIVE]" not in dt_prompt, (
                        f"Directive should not be present when continuity_vector is THREAD_CONTINUATION, got: {dt_prompt}"
                    )

    @pytest.mark.asyncio
    async def test_deep_thought_no_directive_when_no_continuity_vector(self, hub):
        """step_deep_thought does NOT inject directive when continuity_vector is None."""
        hub.turn_thought_trace = {}
        hub.current_interest = 0.8
        hub.current_vibe = "TECHNICAL"
        hub.round_table_memory = []

        recorded_args = []
        async def _mock_process_w_record(*args, **kwargs):
            recorded_args.append(args)
            yield "[thought]Hello world[/thought]"

        with patch.object(hub, "_process_node_stream", side_effect=_mock_process_w_record):
            result = await hub.step_deep_thought(
                query="Any query",
                brain_grounding="",
                interest=0.8,
                shutdown_event=None,
                request_id="default",
            )
            if recorded_args:
                dt_prompt = recorded_args[-1][1] if len(recorded_args[-1]) >= 2 else None
                if dt_prompt:
                    assert "[UNTANGLING_DIRECTIVE]" not in dt_prompt, (
                        f"Directive should not be present when no continuity_vector set"
                    )
