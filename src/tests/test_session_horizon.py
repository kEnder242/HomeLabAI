import pytest
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.v5.foyer.router import FoyerRouter, LAB_VERSION

@pytest.mark.asyncio
async def test_session_token_and_horizon_initialization():
    """Verify session_token is an 8-char hex string and horizon is set to boot time."""
    router = FoyerRouter(disable_ear=True)
    assert len(router.session_token) == 8
    assert router.session_horizon_ts > 0
    assert router.session_horizon_ts <= int(time.time())

@pytest.mark.asyncio
async def test_status_endpoint_contains_session_token():
    """Verify handle_status includes session_token."""
    router = FoyerRouter(disable_ear=True)
    mock_request = MagicMock()
    
    with patch("src.v5.foyer.router.web.json_response") as mock_json_resp:
        await router.handle_status(mock_request)
        assert mock_json_resp.called
        payload = mock_json_resp.call_args[0][0]
        assert "session_token" in payload
        assert payload["session_token"] == router.session_token

@pytest.mark.asyncio
async def test_handshake_updates_horizon_and_returns_sid():
    """Verify handshake sends status payload containing session_token and updated horizon_ts."""
    router = FoyerRouter(disable_ear=True)
    initial_horizon = router.session_horizon_ts
    
    mock_ws = AsyncMock()
    mock_request = MagicMock()
    mock_request.remote = "127.0.0.1"
    mock_request.headers = {}  # Browser case: no initial custom WS header
    
    # Simulate receiving a valid handshake frame
    handshake_payload = json.dumps({
        "type": "handshake",
        "version": LAB_VERSION,
        "client": "intercom",
        "lab_key": router.session_token
    })
    
    mock_msg = MagicMock()
    mock_msg.type = 1 # TEXT (aiohttp.WSMsgType.TEXT)
    mock_msg.data = handshake_payload
    
    async def msg_generator():
        yield mock_msg
        
    mock_ws.__aiter__.side_effect = msg_generator
    
    with patch("aiohttp.web.WebSocketResponse", return_value=mock_ws):
        await router.handle_websocket(mock_request)
        
    assert mock_ws.send_str.called
    sent_data = json.loads(mock_ws.send_str.call_args[0][0])
    assert sent_data["type"] == "status"
    assert sent_data["state"] == "connected"
    assert sent_data["session_token"] == router.session_token
    assert "session_horizon_ts" in sent_data
    assert router.session_horizon_ts >= initial_horizon
