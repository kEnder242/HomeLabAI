import pytest
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nodes.loader import BicameralNode


class _MockContent:
    """Empty async iterable for streaming response content (avoids AttributeError in _stream_vllm)."""
    def __aiter__(self):
        return self
    async def __anext__(self):
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_vllm_lora_request_construction(monkeypatch):
    import aiohttp

    node = BicameralNode("brain", "test prompt")
    node.lora_name = "default_lora"

    # Pre-set engine cache to skip network calls in ping_engine()
    node._engine_cache = {
        "url": "http://localhost:8088/v1/chat/completions",
        "model": "test-model",
        "type": "VLLM",
        "available": ["test-model", "default_lora", "exp_for"]
    }
    node._last_probe = time.time()

    captured_payload = None

    class MockResponse:
        def __init__(self, data):
            self._data = data
            self.status = 200
            self._content = _MockContent()
        async def json(self):
            return self._data
        async def text(self):
            return str(self._data)
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        @property
        def content(self):
            return self._content

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def post(self, url, json, timeout):
            nonlocal captured_payload
            captured_payload = json
            return MockResponse({"choices": [{"message": {"content": "mocked"}}]})

    monkeypatch.setattr("aiohttp.ClientSession", lambda: MockSession())

    async for token in node.generate_response("test query"):
        pass
    assert captured_payload["model"] == "default_lora"

    # metadata does not affect LoRA selection — only role_tokens/lora_name controls the model field
    async for token in node.generate_response("test query", metadata={"expert_adapter": "exp_for"}):
        pass
    assert captured_payload["model"] == "default_lora"


@pytest.mark.asyncio
async def test_role_token_dynamic_swap(monkeypatch):
    import aiohttp

    node = BicameralNode("brain", "test prompt")
    node.lora_name = "default_lora"

    # [BKM-015] Config-driven role tokens: token -> LoRA target mapping
    node.role_tokens = {
        "<|PINKY|>": "cli_voice_v1",
        "<|BRAIN|>": None,  # null target -> base model
    }

    # Pre-set engine cache to skip network calls
    node._engine_cache = {
        "url": "http://localhost:8088/v1/chat/completions",
        "model": "test-model",
        "type": "VLLM",
        "available": ["test-model", "default_lora", "cli_voice_v1", "lab_history_v1"]
    }
    node._last_probe = time.time()

    captured_payload = None

    class MockResponse:
        def __init__(self, data):
            self._data = data
            self.status = 200
            self._content = _MockContent()
        async def json(self):
            return self._data
        async def text(self):
            return str(self._data)
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        @property
        def content(self):
            return self._content

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def post(self, url, json, timeout):
            nonlocal captured_payload
            captured_payload = json
            return MockResponse({"choices": [{"message": {"content": "mocked"}}]})

    monkeypatch.setattr("aiohttp.ClientSession", lambda: MockSession())

    # Test 1: Token present -> stripped from query, LoRA model used
    async for token in node.generate_response("<|PINKY|> test query"):
        pass
    assert captured_payload["model"] == "cli_voice_v1"
    user_msg = captured_payload["messages"][1]["content"]
    assert "<|PINKY|>" not in user_msg
    assert user_msg.strip() == "test query"

    # Test 2: Token with null target -> stripped from query, base model used
    async for token in node.generate_response("<|BRAIN|> another query"):
        pass
    assert captured_payload["model"] == "test-model"
    user_msg = captured_payload["messages"][1]["content"]
    assert "<|BRAIN|>" not in user_msg
    assert user_msg.strip() == "another query"

    # Test 3: No token -> default lora, query unchanged
    async for token in node.generate_response("plain query"):
        pass
    assert captured_payload["model"] == "default_lora"
    user_msg = captured_payload["messages"][1]["content"]
    assert user_msg.strip() == "plain query"
