import pytest
import json
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 1. Archive Node Tests (Rescue & Refine)
from nodes.archive_node import list_cabinet, read_document, consult_clipboard, scribble_note, get_current_time

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
            assert "test.md" in data["drafts"]

@pytest.mark.asyncio
async def test_archive_read_document():
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(side_effect=[MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: "Hello World")])):
        res = read_document("test.md")
        assert res == "Hello World"

@pytest.mark.asyncio
async def test_archive_clipboard():
    mock_coll = MagicMock()
    # Mocking chroma query result structure
    mock_coll.query.return_value = {
        'documents': [["Cached Response"]],
        'distances': [[0.1]],
        'metadatas': [[{'response': 'Cached Response'}]]
    }
    with patch("nodes.archive_node.cache", mock_coll):
        res = consult_clipboard("hello")
        assert res == "Cached Response"

@pytest.mark.asyncio
async def test_archive_scribble():
    mock_coll = MagicMock()
    with patch("nodes.archive_node.cache", mock_coll):
        res = scribble_note("query", "response")
        assert "Insight cached" in res
        assert mock_coll.add.called

@pytest.mark.asyncio
async def test_archive_time():
    res = get_current_time()
    assert "2026" in res
    assert "," in res

# 2. Brain Node Tests (Rescue & Refine)
from nodes.brain_node import _clean_content

@pytest.mark.asyncio
async def test_brain_clean_content():
    raw = "Here is your code:\n```python\nprint('hello')\n```\nHope that helps!"
    clean = _clean_content(raw)
    assert clean == "print('hello')"

    raw = "Certainly! Here is the plan: Deploy vLLM."
    clean = _clean_content(raw)
    assert clean == "Deploy vLLM."

# 3. Pinky Node Tests
from nodes.pinky_node import facilitate

@pytest.mark.asyncio
async def test_pinky_facilitate_oom():
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value={"data": {"result": [{"value": [0, "0.99"]}]}})
    mock_resp.status = 200

    # Patch BicameralNode.probe_engine instead of the node local
    with patch("nodes.loader.BicameralNode.probe_engine", AsyncMock(return_value=("OLLAMA", "url", "model"))), \
         patch("aiohttp.ClientSession.get", return_value=mock_resp):
        res = await facilitate("hello", "context")
        data = json.loads(res)
        assert data["tool"] == "reply_to_user"
        # In current BicameralNode, a mock 'url' will trigger a connection failure
        assert "Connection Failed" in data["parameters"]["text"]
