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
    with patch("nodes.archive_node.wisdom.query") as mock_wisdom, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock(side_effect=[MagicMock(__enter__=lambda s: s, __exit__=lambda s, *a: None, read=lambda: '[{"summary": "Test Summary", "rank": 4}]')])):
        
        mock_wisdom.return_value = {'documents': [["Strategic Pillar 1"]]}
        
        res = build_cv_summary("2024")
        assert "STRATEGIC PILLARS (2024):" in res
        assert "Strategic Pillar 1" in res
        assert "TECHNICAL EVIDENCE (2024):" in res
        assert "Test Summary" in res

@pytest.mark.asyncio
async def test_access_personal_history():
    with patch("nodes.archive_node.peek_related_notes", return_value="Historical Fact") as mock_peek:
        res = access_personal_history("keyword")
        assert res == "Historical Fact"
        mock_peek.assert_called_with("keyword")

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
