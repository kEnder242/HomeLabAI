"""[FEAT-519] Unit Test: Triage Context Squeeze & Token Cap."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_triage_strips_round_table_memory():
    from logic.cognitive_hub import CognitiveHub
    
    hub = CognitiveHub.__new__(CognitiveHub)
    hub.round_table_memory = ["Brain: Previous thought 1", "Pinky: Previous thought 2"]
    hub.residents = {}
    hub.session_buffers = {}
    hub.current_interest = 0.0
    hub.broadcast = AsyncMock()
    
    mock_node = MagicMock()
    captured_args = {}
    async def mock_call_tool(name, arguments):
        nonlocal captured_args
        captured_args = arguments
        return "mock_resp"
    mock_node.call_tool = mock_call_tool
    hub.residents["lab"] = mock_node
    
    # 1. Test Triage Call
    tokens = []
    async def run_triage():
        async for t in hub._process_node_stream("lab", "Hello test", "", "Lab (Triage)"):
            tokens.append(t)
    
    try:
        await asyncio.wait_for(run_triage(), timeout=0.2)
    except (asyncio.TimeoutError, Exception):
        pass
        
    assert "[PREVIOUS_DEBATE]" not in captured_args.get("query", "")
    assert captured_args.get("max_tokens") == 128
    
    # 2. Test Standard Call (Pinky)
    captured_args.clear()
    async def run_standard():
        async for t in hub._process_node_stream("lab", "Hello test", "", "Pinky"):
            tokens.append(t)
            
    try:
        await asyncio.wait_for(run_standard(), timeout=0.2)
    except (asyncio.TimeoutError, Exception):
        pass
        
    assert "[PREVIOUS_DEBATE]" in captured_args.get("query", "")
    assert captured_args.get("max_tokens") == 1000

@pytest.mark.asyncio
async def test_generate_response_max_tokens_default():
    from nodes.loader import BicameralNode
    
    node = BicameralNode.__new__(BicameralNode)
    node.name = "TestNode"
    # Verify generate_response signature has max_tokens=1000 default
    import inspect
    sig = inspect.signature(node.generate_response)
    assert "max_tokens" in sig.parameters
    assert sig.parameters["max_tokens"].default == 1000
