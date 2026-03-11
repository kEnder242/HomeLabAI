import pytest
import json
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add src to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.archive_node import build_cv_summary, access_personal_history
from nodes.architect_node import generate_bkm
from nodes.pinky_node import start_draft

@pytest.mark.asyncio
async def test_build_cv_summary():
    mock_data = {"test": "data"}
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: json.dumps(mock_data)))):
        
        res = await build_cv_summary()
        data = json.loads(res)
        assert data["test"] == "data"

@pytest.mark.asyncio
async def test_access_personal_history():
    mock_event = {"topic": "Test Topic", "context": "Test Context", "successful": True}
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, __iter__=lambda s: iter([json.dumps(mock_event)])))):
        
        res = await access_personal_history("Test")
        data = json.loads(res)
        assert len(data) == 1
        assert data[0]["topic"] == "Test Topic"

@pytest.mark.asyncio
async def test_generate_bkm():
    res = await generate_bkm("vLLM", "deployment")
    assert "# BKM: VLLM" in res
    assert "**Category:** Deployment" in res
    assert "Execution" in res

@pytest.mark.asyncio
async def test_pinky_start_draft():
    # This just returns JSON for the hub
    res = await start_draft("vLLM", "deployment")
    data = json.loads(res)
    assert data["tool"] == "generate_bkm"
    assert data["parameters"]["topic"] == "vLLM"
