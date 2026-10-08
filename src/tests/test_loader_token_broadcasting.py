"""Unit test verifying Story 101.4: Abolition of stream_source = None token gagging."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from nodes.loader import BicameralNode


@pytest.mark.asyncio
async def test_loader_internal_tokens_broadcast_with_channel_tag():
    # Setup node with mocked MCP
    mock_mcp = MagicMock()
    # Capture tool decorator
    tool_funcs = {}
    def tool_dec():
        def reg(fn):
            tool_funcs[fn.__name__] = fn
            return fn
        return reg
    mock_mcp.tool = tool_dec

    with patch("nodes.loader.FastMCP", return_value=mock_mcp):
        node = BicameralNode("brain", "You are Brain.")

    # Mock _broadcast_token
    node._broadcast_token = MagicMock()

    # Mock generate_response as async generator
    async def mock_gen(*args, **kwargs):
        yield "token1"
        yield "token2"

    node.generate_response = mock_gen

    # Execute think with internal=True
    think_fn = tool_funcs["think"]
    res = await think_fn("test query", internal=True)

    # Invariant 1: Full response returned
    assert res == "token1token2"

    # Invariant 2: _broadcast_token was called for each token with channel="crosstalk" and is_internal=True
    assert node._broadcast_token.call_count >= 2
    for call in node._broadcast_token.call_args_list:
        kwargs = call.kwargs
        assert kwargs.get("channel") == "crosstalk"
        assert kwargs.get("is_internal") is True
        assert call.args[1] == "brain"  # source_name is NOT None!
