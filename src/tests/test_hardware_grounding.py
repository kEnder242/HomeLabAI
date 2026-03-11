import pytest
import sys
import os
import json
import aiohttp
from unittest.mock import patch, AsyncMock

# Adjust sys.path to find nodes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nodes.archive_node import get_lab_health, vram_vibe_check
from nodes.loader import BicameralNode

@pytest.mark.asyncio
async def test_get_lab_health_mock():
    mock_heartbeat = {
        "status": "online",
        "gpu": {"vram_used_mb": 4096, "vram_total_mb": 11264, "temperature": 55}
    }
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_heartbeat
        mock_get.return_value.__aenter__.return_value = mock_response
        
        res = await get_lab_health()
        data = json.loads(res)
        assert data["status"] == "online"
        assert data["gpu"]["vram_used_mb"] == 4096

@pytest.mark.asyncio
async def test_vram_vibe_check_mock():
    mock_heartbeat = {
        "status": "online",
        "gpu": {"vram_used_mb": 5000, "vram_total_mb": 10000, "temperature": 60}
    }
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_heartbeat
        mock_get.return_value.__aenter__.return_value = mock_response
        
        res = await vram_vibe_check()
        assert "VRAM: 5000MB / 10000MB (50.0%)" in res
        assert "Temp: 60C" in res

@pytest.mark.asyncio
async def test_ping_engine_mock():
    node = BicameralNode("test", "test prompt")
    
    # Mock probe_engine to return OLLAMA
    node.probe_engine = AsyncMock(return_value=("OLLAMA", "http://localhost:11434/api/chat", "llama3"))
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response
        
        success, msg = await node.ping_engine()
        assert success is True
        assert "Ollama 200" in msg
