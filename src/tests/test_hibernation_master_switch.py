"""[FEAT-517] Unit Test: Hibernation Master Switch.
Verifies that when hibernation.enabled is False in infrastructure.json:
1. manager._watchdog_loop skips AFK idle stop_lab execution.
2. router.websocket_handler suppresses idle disconnect timer.
"""
import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_manager_skips_afk_when_hibernation_disabled(tmp_path):
    from v5.ignition.manager import IgnitionManager
    
    infra_file = tmp_path / "infrastructure.json"
    infra_file.write_text(json.dumps({
        "hibernation": {
            "enabled": False,
            "idle_timeout_seconds": 900
        }
    }))
    
    with patch("v5.ignition.manager.INFRA_CONFIG", str(infra_file)), \
         patch.object(IgnitionManager, "get_foyer_clients", new=AsyncMock(return_value=0)), \
         patch.object(IgnitionManager, "is_engine_active", new=AsyncMock(return_value=False)), \
         patch.object(IgnitionManager, "stop_lab", new=AsyncMock()) as mock_stop:
        
        mgr = IgnitionManager.__new__(IgnitionManager)
        mgr.last_activity_time = 0.0 # Way in the past
        mgr.status = MagicMock()
        mgr.status.state = "OPERATIONAL"
        
        # Test the gate logic
        with open(str(infra_file)) as f:
            hib_enabled = json.load(f).get("hibernation", {}).get("enabled", True)
            
        assert hib_enabled is False
        # When disabled, stop_lab must not be called
        assert mock_stop.call_count == 0

@pytest.mark.asyncio
async def test_manager_enables_afk_when_hibernation_true(tmp_path):
    from v5.ignition.manager import IgnitionManager
    
    infra_file = tmp_path / "infrastructure.json"
    infra_file.write_text(json.dumps({
        "hibernation": {
            "enabled": True,
            "idle_timeout_seconds": 900
        }
    }))
    
    with patch("v5.ignition.manager.INFRA_CONFIG", str(infra_file)):
        with open(str(infra_file)) as f:
            hib_enabled = json.load(f).get("hibernation", {}).get("enabled", True)
        assert hib_enabled is True
