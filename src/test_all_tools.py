import pytest
import json
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to path for imports
sys.path.append(os.path.dirname(__file__))

# 1. Archive Node Tests
from nodes.archive_node import list_cabinet, read_document

@pytest.mark.asyncio
async def test_archive_list_cabinet():
    with patch("nodes.archive_node.SEARCH_INDEX", "fake_index.json"), \
         patch("nodes.archive_node.DRAFTS_DIR", "/tmp/drafts"), \
         patch("nodes.archive_node.WORKSPACE_DIR", "/tmp/workspace"), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(side_effect=[MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: '{"2019": ["file1"]}')])):
        
        with patch("glob.glob", return_value=["/tmp/drafts/test.md"]):
            res = list_cabinet()
            data = json.loads(res)
            assert "archive" in data
            assert "2019" in data["archive"]
            # list_cabinet returns basenames
            assert "test.md" in data["drafts"]

@pytest.mark.asyncio
async def test_archive_read_document():
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(side_effect=[MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: "Hello World")])):
        res = read_document("test.md")
        assert res == "Hello World"

# 2. Brain Node Tests
from nodes.brain_node import write_draft, _clean_content

@pytest.mark.asyncio
async def test_brain_clean_content():
    # Test code block extraction
    raw = "Here is your code:\n```python\nprint('hello')\n```\nHope that helps!"
    clean = _clean_content(raw)
    assert clean == "print('hello')"
    
    # Test chatter stripping
    raw = "Certainly! Here is the plan: Deploy vLLM."
    clean = _clean_content(raw)
    assert clean == "Deploy vLLM."

@pytest.mark.asyncio
async def test_brain_write_draft():
    with patch("nodes.brain_node.DRAFTS_DIR", "/tmp"), \
         patch("os.path.exists", return_value=False), \
         patch("builtins.open", MagicMock()):
        res = await write_draft("plan.md", "content")
        assert "[THE EDITOR]" in res

# 3. Pinky Node Tests
from nodes.pinky_node import facilitate

@pytest.mark.asyncio
async def test_pinky_facilitate_oom():
    # Simulate VRAM > 95%
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value={"data": {"result": [{"value": [0, "0.96"]}]}})
    mock_resp.status = 200
    
    # We need to mock the probe_engine too so it doesn't try to connect
    with patch("nodes.pinky_node.probe_engine", AsyncMock(return_value=("OLLAMA", "url", "model"))), \
         patch("aiohttp.ClientSession.get", return_value=mock_resp):
        res = await facilitate("hello", "context")
        data = json.loads(res)
        assert data["tool"] == "reply_to_user"
        assert "OOM" in data["parameters"]["text"]

@pytest.mark.asyncio
async def test_pinky_facilitate_routing():
    with patch("nodes.pinky_node.probe_engine", AsyncMock(return_value=("OLLAMA", "url", "model"))), \
         patch("aiohttp.ClientSession.get") as mock_get, \
         patch("aiohttp.ClientSession.post") as mock_post:
        
        # 1. Mock VRAM check (low)
        vram_resp = AsyncMock()
        vram_resp.json = AsyncMock(return_value={"data": {"result": [{"value": [0, "0.5"]}]}})
        vram_resp.status = 200
        mock_get.return_value.__aenter__.return_value = vram_resp

        # 2. Mock LLM response
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"response": '{"tool": "reply_to_user", "parameters": {"text": "Narf!"}}'})
        mock_post.return_value.__aenter__.return_value = mock_resp
        
        res = await facilitate("hello", "context")
        assert "Narf!" in res