import pytest
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nodes.loader import BicameralNode

@pytest.mark.asyncio
async def test_vllm_lora_request_construction(monkeypatch):
    import aiohttp
    
    node = BicameralNode("brain", "test prompt")
    node.lora_name = "default_lora"
    
    async def mock_probe(*args, **kwargs):
        return ("VLLM", "http://localhost:8088/v1/chat/completions", "test-model")
    node.probe_engine = mock_probe
    node._patch_model = lambda x: None

    captured_payload = None

    class MockResponse:
        def __init__(self, data):
            self._data = data
            self.status = 200
        async def json(self):
            return self._data
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass

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
    monkeypatch.setattr("os.path.exists", lambda x: True)

    await node.generate_response("test query")
    assert captured_payload["lora_request"]["name"] == "default_lora"

    await node.generate_response("test query", metadata={"expert_adapter": "exp_for"})
    assert captured_payload["lora_request"]["name"] == "exp_for"
