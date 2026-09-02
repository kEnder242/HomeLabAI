import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from v5.ignition.manager import IgnitionManager

@pytest.mark.asyncio
async def test_boot_when_hibernation_disabled():
    mgr = IgnitionManager()
    mgr.queue_watcher = AsyncMock()
    mgr.continuous_burn_loop = AsyncMock()
    mgr.journal_monitor = AsyncMock()
    mgr.start_lab = AsyncMock()
    mgr.update_status_file = MagicMock()
    test_infra = {"hibernation": {"enabled": False, "daytime_node_residency": "ON_DEMAND"}}
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()), \
         patch("json.load", return_value=test_infra), \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        try:
            await mgr.main_loop()
        except asyncio.CancelledError:
            pass
    mgr.start_lab.assert_called_once_with(reason="BOOT_PERMANENT_RESIDENT")

@pytest.mark.asyncio
async def test_boot_when_permanent_resident():
    mgr = IgnitionManager()
    mgr.queue_watcher = AsyncMock()
    mgr.continuous_burn_loop = AsyncMock()
    mgr.journal_monitor = AsyncMock()
    mgr.start_lab = AsyncMock()
    mgr.update_status_file = MagicMock()
    test_infra = {"hibernation": {"enabled": True, "daytime_node_residency": "PERMANENT_RESIDENT"}}
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()), \
         patch("json.load", return_value=test_infra), \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        try:
            await mgr.main_loop()
        except asyncio.CancelledError:
            pass
    mgr.start_lab.assert_called_once_with(reason="BOOT_PERMANENT_RESIDENT")

@pytest.mark.asyncio
async def test_boot_when_hibernation_enabled_and_on_demand():
    mgr = IgnitionManager()
    mgr.queue_watcher = AsyncMock()
    mgr.continuous_burn_loop = AsyncMock()
    mgr.journal_monitor = AsyncMock()
    mgr.start_lab = AsyncMock()
    mgr.update_status_file = MagicMock()
    test_infra = {"hibernation": {"enabled": True, "daytime_node_residency": "ON_DEMAND"}}
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()), \
         patch("json.load", return_value=test_infra), \
         patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        try:
            await mgr.main_loop()
        except asyncio.CancelledError:
            pass
    mgr.start_lab.assert_not_called()
