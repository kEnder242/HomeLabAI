import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from lab_attendant import LabAttendant

class TestSafePilot(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.attendant = LabAttendant()
        self.attendant.handle_start = AsyncMock()
        self.attendant._get_current_vitals = AsyncMock(return_value={
            "lab_server_running": False
        })

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("lab_attendant.current_lab_mode", "OFFLINE")
    async def test_ignition_success(self, mock_sleep):
        """Verify ignition triggers when VRAM is low."""
        self.attendant._get_vram_info = AsyncMock(return_value=(300, 11000))
        
        await self.attendant._safe_pilot_ignition()
        
        mock_sleep.assert_awaited_once_with(60)
        self.attendant.handle_start.assert_called_once()
        print("[PASS] Ignition triggered correctly on low VRAM.")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("lab_attendant.current_lab_mode", "OFFLINE")
    async def test_ignition_aborted_vram(self, mock_sleep):
        """Verify ignition aborts when VRAM is high."""
        self.attendant._get_vram_info = AsyncMock(return_value=(2500, 11000))
        
        await self.attendant._safe_pilot_ignition()
        
        self.attendant.handle_start.assert_not_called()
        print("[PASS] Ignition aborted correctly on high VRAM (>1GB).")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("lab_attendant.current_lab_mode", "vLLM")
    async def test_ignition_aborted_active(self, mock_sleep):
        """Verify ignition aborts if lab is already active."""
        self.attendant._get_vram_info = AsyncMock(return_value=(300, 11000))
        
        await self.attendant._safe_pilot_ignition()
        
        self.attendant.handle_start.assert_not_called()
        print("[PASS] Ignition aborted correctly when Lab already active.")

if __name__ == "__main__":
    asyncio.run(unittest.main())
