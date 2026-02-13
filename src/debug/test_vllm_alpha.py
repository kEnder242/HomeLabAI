import pytest
import os
import sys
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from nodes.brain_node import node

@pytest.mark.asyncio
async def test_vllm_routing_logic():
    """Verifies that BicameralNode correctly probes the engine."""
    
    # 1. Test Environment Override
    os.environ["BRAIN_ENGINE"] = "VLLM"
    engine, url, model = await node.probe_engine()
    assert engine == "VLLM"
    assert "8088" in url
    
    os.environ["BRAIN_ENGINE"] = "OLLAMA"
    engine, url, model = await node.probe_engine()
    assert engine == "OLLAMA"
    assert "11434" in url

    # Cleanup
    del os.environ["BRAIN_ENGINE"]
