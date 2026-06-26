import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add src directory to path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from v5.ignition.manager import IgnitionManager

class TestTieredIdleVerification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = IgnitionManager()
        # Set operational start time to a past value to bypass settle window by default
        self.manager.operational_start_time = 1.0 

    @patch("os.path.exists")
    async def test_vllm_not_running_no_pid(self, mock_exists):
        mock_exists.return_value = False
        is_active = await self.manager.is_engine_active()
        self.assertFalse(is_active)

    @patch("os.path.exists")
    @patch("psutil.pid_exists")
    async def test_vllm_pid_not_exists(self, mock_pid_exists, mock_exists):
        mock_exists.return_value = True
        mock_pid_exists.return_value = False
        
        with patch("builtins.open", mock_open(read_data="12345")):
            is_active = await self.manager.is_engine_active()
            self.assertFalse(is_active)

    @patch("os.path.exists")
    @patch("psutil.pid_exists")
    @patch("psutil.Process")
    async def test_tier1_zero_connections(self, mock_process, mock_pid_exists, mock_exists):
        mock_exists.return_value = True
        mock_pid_exists.return_value = True
        
        # Mock process with zero established connections on port 8088
        mock_proc_instance = MagicMock()
        mock_proc_instance.connections.return_value = []
        mock_process.return_value = mock_proc_instance
        
        with patch("builtins.open", mock_open(read_data="12345")):
            is_active = await self.manager.is_engine_active()
            self.assertFalse(is_active)

    @patch("os.path.exists")
    @patch("psutil.pid_exists")
    @patch("psutil.Process")
    @patch("urllib.request.urlopen")
    async def test_tier2_connections_but_metrics_idle(self, mock_urlopen, mock_process, mock_pid_exists, mock_exists):
        mock_exists.return_value = True
        mock_pid_exists.return_value = True
        
        # Mock established connection on port 8088
        conn = MagicMock()
        conn.status = "ESTABLISHED"
        conn.laddr.port = 8088
        
        mock_proc_instance = MagicMock()
        mock_proc_instance.connections.return_value = [conn]
        mock_process.return_value = mock_proc_instance
        
        # Mock vLLM metrics response with 0 active requests
        mock_response = MagicMock()
        mock_response.read.return_value = b"""
# HELP vllm:num_requests_running Number of running requests
# TYPE vllm:num_requests_running gauge
vllm:num_requests_running 0.0
# HELP vllm:num_requests_waiting Number of waiting requests
# TYPE vllm:num_requests_waiting gauge
vllm:num_requests_waiting 0.0
"""
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with patch("builtins.open", mock_open(read_data="12345")):
            is_active = await self.manager.is_engine_active()
            self.assertFalse(is_active)

    @patch("os.path.exists")
    @patch("psutil.pid_exists")
    @patch("psutil.Process")
    @patch("urllib.request.urlopen")
    async def test_tier2_active_requests(self, mock_urlopen, mock_process, mock_pid_exists, mock_exists):
        mock_exists.return_value = True
        mock_pid_exists.return_value = True
        
        conn = MagicMock()
        conn.status = "ESTABLISHED"
        conn.laddr.port = 8088
        
        mock_proc_instance = MagicMock()
        mock_proc_instance.connections.return_value = [conn]
        mock_process.return_value = mock_proc_instance
        
        # Mock metrics response with 2 running requests
        mock_response = MagicMock()
        mock_response.read.return_value = b"vllm:num_requests_running 2.0\nvllm:num_requests_waiting 0.0"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with patch("builtins.open", mock_open(read_data="12345")):
            is_active = await self.manager.is_engine_active()
            self.assertTrue(is_active)

    @patch("time.time")
    async def test_settle_window_active(self, mock_time):
        mock_time.return_value = 100.0
        self.manager.operational_start_time = 80.0  # 20s uptime (<60s settle window)
        
        is_active = await self.manager.is_engine_active()
        self.assertTrue(is_active)

if __name__ == "__main__":
    unittest.main()
