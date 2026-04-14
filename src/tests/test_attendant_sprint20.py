import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
import logging

# Mock FastMCP before importing
sys.modules['mcp.server.fastmcp'] = MagicMock()

from src.lab_attendant_v4 import LabAttendantV4

@pytest.fixture
def attendant():
    with patch("src.lab_attendant_v4.reclaim_logger"):
        with patch("src.lab_attendant_v4.pynvml"):
            with patch("src.lab_attendant_v4.check_singleton"):
                with patch("src.lab_attendant_v4.get_style_key", return_value="mock_key"):
                    inst = LabAttendantV4()
                    yield inst

@pytest.mark.asyncio
async def test_wait_ready_timeout_extension(attendant):
    """Verify Task 4: wait_ready default timeout is 480."""
    # Check the method signature or default value
    assert attendant.mcp_wait_ready.__defaults__[0] == 480

@pytest.mark.asyncio
async def test_hibernation_logging_forensic(attendant):
    """Verify Task 5: Forensic logging in mcp_hibernate."""
    # Success response for prefix reset
    mock_resp_ok = AsyncMock()
    mock_resp_ok.status = 200
    mock_resp_ok.__aenter__.return_value = mock_resp_ok

    # Error response for sleep call
    mock_resp_err = AsyncMock()
    mock_resp_err.status = 500
    mock_resp_err.text.return_value = "Forensic Error Body"
    mock_resp_err.__aenter__.return_value = mock_resp_err
    
    mock_session = MagicMock()
    mock_session.post.side_effect = [mock_resp_ok, mock_resp_err]
    mock_session.__aenter__.return_value = mock_session
    
    # Patch the base Logger.error method to capture ALL error calls
    with patch("logging.Logger.error") as mock_error:
        with patch.object(LabAttendantV4, "update_status_json", AsyncMock()):
            with patch("aiohttp.ClientSession", return_value=mock_session):
                await attendant.mcp_hibernate(reason="TEST")
                
                # Check for error log with body
                # The logger call is: logger.error(f"[{self.session_token}] [SLEEP] Level 2 rejected ({r.status}): {err_body}")
                calls = [call.args[0] for call in mock_error.call_args_list]
                assert any("Level 2 rejected (500): Forensic Error Body" in str(c) for c in calls)
