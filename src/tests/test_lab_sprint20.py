import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from src.acme_lab import AcmeLab

@pytest.fixture
async def lab():
    # Mocking singleton lock and aiohttp to avoid real side-effects
    with patch("os.open", return_value=999):
        with patch("os.fdopen", mock_open()):
            with patch("psutil.pid_exists", return_value=False):
                with patch("aiohttp.ClientSession"):
                    lab_inst = AcmeLab(role="TEST")
                    # Ensure we don't start any real background loops
                    lab_inst.status = "READY"
                    lab_inst.engine_ready.set()
                    yield lab_inst
                    # Cleanup
                    if hasattr(lab_inst, "shutdown_event"):
                        lab_inst.shutdown_event.set()

@pytest.mark.asyncio
async def test_neural_buffer_queuing(lab):
    """Verify FEAT-283: Neural Buffer queues queries during WAKING."""
    lab.status = "WAKING"
    lab.engine_ready.clear() # Simulate engine not yet ready
    
    # Mock a websocket
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    
    query = "Delayed query for the buffer."
    
    # Simulate the logic in client_handler for text_input
    if lab.status == "WAKING":
        await lab._neural_queue.put(query)
        await ws.send_json({
            "type": "status",
            "message": "Queued",
            "state": "lobby"
        })
    
    assert lab._neural_queue.qsize() == 1
    
    # Now verify draining
    lab.status = "OPERATIONAL"
    lab.engine_ready.set()
    lab.process_query = AsyncMock()
    
    await lab._drain_neural_buffer()
    assert lab._neural_queue.qsize() == 0
    lab.process_query.assert_called_with(query)

@pytest.mark.asyncio
async def test_heartbeat_deferral(lab):
    """Verify FEAT-283.2: Heartbeat Deferral during WAKING/HIBERNATING."""
    # 1. Normal state
    lab.status = "READY"
    lab.broadcast = AsyncMock() # Mock broadcast to avoid real calls
    
    # Mock aiohttp.ClientSession context manager
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {"models": [{"name": "test"}]}
    mock_resp.__aenter__.return_value = mock_resp

    mock_session = MagicMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    
    with patch("src.acme_lab.resolve_brain_url", return_value="http://localhost"):
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await lab.check_brain_health(force=False)
            assert mock_session.get.called
            assert lab.brain_online is True

    # 2. WAKING state
    lab.status = "WAKING"
    mock_session.get.reset_mock()
    with patch("aiohttp.ClientSession", return_value=mock_session):
        await lab.check_brain_health(force=False)
        assert not mock_session.get.called # Should have deferred

    # 3. HIBERNATING state
    lab.status = "HIBERNATING"
    mock_session.get.reset_mock()
    with patch("aiohttp.ClientSession", return_value=mock_session):
        await lab.check_brain_health(force=False)
        assert not mock_session.get.called # Should have deferred

    # 4. Forced check even when hibernating
    mock_session.get.reset_mock()
    with patch("src.acme_lab.resolve_brain_url", return_value="http://localhost"):
        with patch("aiohttp.ClientSession", return_value=mock_session):
            await lab.check_brain_health(force=True)
            assert mock_session.get.called # Should have bypassed deferral
