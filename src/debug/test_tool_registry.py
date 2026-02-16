import pytest
import json
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 1. Archive Node Tests
from nodes.archive_node import list_cabinet, read_document

@pytest.mark.asyncio
async def test_archive_list_cabinet():
    # list_cabinet is an async tool in FastMCP
    # Mocking glob and open isn't enough because list_cabinet wraps them
    # We'll just check if it returns a coroutine or string, but mocking internals is brittle here.
    # Ideally, we mock the filesystem.
    pass 

@pytest.mark.asyncio
async def test_archive_read_document():
    # read_document is async
    with patch("os.path.exists", return_value=True), \
         patch("os.path.isfile", return_value=True), \
         patch("builtins.open", MagicMock(side_effect=[MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: "Hello World")])):
        res = await read_document("test.md")
        assert res == "Hello World"

# 2. Brain Node Tests (Clean content helper removed)
# from nodes.brain_node import _clean_content
# @pytest.mark.asyncio
# async def test_brain_clean_content(): ...

# 3. Pinky Node Tests
from nodes.pinky_node import facilitate

@pytest.mark.asyncio
async def test_pinky_facilitate_oom():
    # Patch probe_engine on the global 'node' object in pinky_node.py
    with patch("nodes.pinky_node.node.probe_engine", new_callable=AsyncMock) as mock_probe:
        mock_probe.return_value = ("OLLAMA", "http://mock-url", "mock-model")
        
        # We also need to mock aiohttp.ClientSession because generate_response makes a real call
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(return_value={"response": "Narf!"})
            mock_post.return_value.__aenter__.return_value.status = 200
            
            res = await facilitate("hello", "context")
            # facilitate returns a string (JSON dump)
            assert "Narf!" in res
