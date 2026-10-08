import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

try:
    from v5.ignition.manager import IgnitionManager, LabStatus
except (ImportError, ModuleNotFoundError):
    pytest.skip("IgnitionManager not available", allow_module_level=True)


class TestIgnitionManagerKillGuardrail:
    """Test the Ignition Kill Guardrail feature (Story 101.6)."""

    @pytest.fixture
    def manager(self):
        """Create an IgnitionManager instance for testing."""
        status = LabStatus()
        manager = IgnitionManager(status=status)
        return manager

    def test_readiness_probe_loop_range(self):
        """Verify the readiness probe loop uses range(360) for 30-minute timeout."""
        source_file = os.path.join(
            os.path.dirname(__file__), 
            '..', 'v5', 'ignition', 'manager.py'
        )
        
        with open(source_file, 'r') as f:
            content = f.read()
            
        lines = content.split('\n')
        in_start_lab = False
        found = False
        for i, line in enumerate(lines):
            if 'async def start_lab(self, reason="INTENT"):' in line:
                in_start_lab = True
            elif in_start_lab and 'def ' in line and line.strip().startswith('def '):
                break
            elif in_start_lab and 'for _ in range(360):' in line:
                # Verify the comment too
                assert 'Up to 30 minutes at 5s polling intervals' in lines[i], \
                    f"Missing expected comment at line {i}: {lines[i]}"
                found = True
                break
                
        assert found, "Could not find readiness probe loop with range(360) in start_lab method"

    def test_kill_stale_vllm_method_exists(self, manager):
        """Verify _kill_stale_vllm method exists on IgnitionManager."""
        assert hasattr(manager, '_kill_stale_vllm')
        assert callable(getattr(manager, '_kill_stale_vllm'))

    def test_kill_stale_vllm_calls_subprocess(self, manager):
        """Test that _kill_stale_vllm calls the expected subprocess commands."""
        with patch('subprocess.run') as mock_subprocess, \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', MagicMock()), \
             patch('psutil.pid_exists', return_value=True), \
             patch('psutil.Process') as mock_process, \
             patch('time.sleep'):
            
            mock_file = MagicMock()
            mock_file.read.return_value = '12345'
            mock_file.__enter__.return_value = mock_file
            mock_file.__exit__.return_value = None
            
            with patch('builtins.open', return_value=mock_file):
                manager._kill_stale_vllm()
                
                assert mock_subprocess.call_count >= 3
                calls = [call.args[0] for call in mock_subprocess.call_args_list]
                assert any('sudo' in str(call) and 'kill' in str(call) and '-9' in str(call) for call in calls)
                assert any('sudo' in str(call) and 'pkill' in str(call) and 'vllm.entrypoints.openai.api_server' in str(call) for call in calls)
                assert any('sudo' in str(call) and 'pkill' in str(call) and 'VLLM::EngineCore' in str(call) for call in calls)

    def test_kill_stale_vllm_signature(self, manager):
        """Test that _kill_stale_vllm is callable with zero required arguments."""
        import inspect
        sig = inspect.signature(IgnitionManager._kill_stale_vllm)
        params = list(sig.parameters.keys())
        assert params == ['self'], f"Expected only 'self' parameter, got {params}"

    def test_kill_stale_vllm_called_on_timeout(self, manager):
        """Test that _kill_stale_vllm is called when readiness probe times out."""
        async def run_test():
            with patch('subprocess.Popen'), \
                 patch('urllib.request.urlopen', side_effect=Exception("Connection failed")), \
                 patch('asyncio.sleep'), \
                 patch.object(manager, '_kill_stale_vllm') as mock_kill, \
                 patch.object(manager, '_release_vram_lock'), \
                 patch.object(manager, 'update_status_file'), \
                 patch('builtins.range', return_value=range(1)):
                result = await manager.start_lab(reason="TEST")
                assert result is False
                mock_kill.assert_called_once()
                manager._release_vram_lock.assert_called_once()

        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
