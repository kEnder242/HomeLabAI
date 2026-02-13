import os
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from nodes.brain_node import deep_think

@pytest.mark.asyncio
async def test_vllm_routing_logic():
    """Verifies that brain_node routes to the correct internal method based on ENV."""
    
    # 1. Test Ollama Routing (Default)
    os.environ["USE_BRAIN_VLLM"] = "0"
    with patch("nodes.brain_node.deep_think_ollama", return_value="Ollama Success") as mock_ollama:
        res = await deep_think("test")
        assert res == "Ollama Success"
        mock_ollama.assert_called_once()
    
    # 2. Test vLLM Routing
    os.environ["USE_BRAIN_VLLM"] = "1"
    with patch("nodes.brain_node.deep_think_vllm", return_value="vLLM Success") as mock_vllm:
        res = await deep_think("test")
        assert res == "vLLM Success"
        mock_vllm.assert_called_once()
    
    print("[PASS] Routing logic verified via mocks.")

if __name__ == "__main__":
    asyncio.run(test_vllm_routing_logic())
