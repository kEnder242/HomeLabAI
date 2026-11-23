# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nodes.loader import BicameralNode
from logic.cognitive_hub import CognitiveHub


class MockAsyncContextManager:
    def __init__(self, target):
        self.target = target

    async def __aenter__(self):
        return self.target

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_bicameral_node_prewarm_omlx():
    """Verify BicameralNode prewarm dispatches to active OMLX/OpenAI engine with max_tokens=1."""
    node = BicameralNode("Thought", "System Prompt Ground Truth")
    node._engine_cache = {
        "url": "http://192.168.1.46:8002/v1/chat/completions",
        "model": "TokenAI-zer--Ternary-Bonsai-2-27B-MLX-oQ2-mtp",
        "type": "OMLX",
        "host": "M5_AIR",
    }

    mock_resp = MagicMock()
    mock_resp.status = 200

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=MockAsyncContextManager(mock_resp))
    mock_session_cls = MagicMock(return_value=MockAsyncContextManager(mock_session))

    with patch("aiohttp.ClientSession", mock_session_cls):
        success = await node.prewarm("What is PECI?", static_context="Topology ground truth", request_id="test_req")
        assert success is True
        assert mock_session.post.called
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://192.168.1.46:8002/v1/chat/completions"
        payload = call_args[1]["json"]
        assert payload["max_tokens"] == 1
        assert payload["enable_thinking"] is False
        assert "[STATIC_ANCHORS]:" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_bicameral_node_prewarm_ollama_kender():
    """Verify BicameralNode prewarm dispatches to active Ollama/KENDER engine."""
    node = BicameralNode("Thought", "System Prompt Ground Truth")
    node._engine_cache = {
        "url": "http://192.168.1.26:11434/api/chat",
        "model": "qwen3.8:nothink",
        "type": "OLLAMA",
        "host": "KENDER",
    }

    mock_resp = MagicMock()
    mock_resp.status = 200

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=MockAsyncContextManager(mock_resp))
    mock_session_cls = MagicMock(return_value=MockAsyncContextManager(mock_session))

    with patch("aiohttp.ClientSession", mock_session_cls):
        success = await node.prewarm("What is MCTP?", request_id="test_req")
        assert success is True
        assert mock_session.post.called
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://192.168.1.26:11434/api/chat"
        payload = call_args[1]["json"]
        assert payload["options"]["num_predict"] == 1


@pytest.mark.asyncio
async def test_step_deep_thought_includes_drop_reminder():
    """Verify step_deep_thought appends drop reminder delta into prompt parts."""
    hub = CognitiveHub.__new__(CognitiveHub)
    hub.residents = {"thought": MagicMock()}
    hub.turn_thought_trace = {}
    hub.current_interest = 0.8
    hub.broadcast = AsyncMock()

    captured_prompt = []

    async def mock_stream(node_id, prompt, *args, **kwargs):
        captured_prompt.append(prompt)
        yield "Deep Thought synthesized reality."

    hub._process_node_stream = mock_stream

    drop_directive = "[CURATOR_DROP_REMINDER]: Brain evaluated candidate evidence and discarded 1 irrelevant chunks: CHUNK-2."
    result = await hub.step_deep_thought(
        query="PECI test suite status",
        brain_grounding="CHUNK-1 bedrock",
        interest=0.8,
        drop_reminder=drop_directive,
    )
    assert result == "Deep Thought synthesized reality."
    assert len(captured_prompt) == 1
    assert drop_directive in captured_prompt[0]
