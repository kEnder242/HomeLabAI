"""
Sprint 60 In-Process Integration Test Suite.
Tests the end-to-end integration of the three decoupled satellites:
1. OverrideParser Satellite (FEAT-145/REF-01)
2. MaintenanceSweeper Satellite (LAB-095/LAB-096/LAB-099/REF-02)
3. AudioPipeline Satellite (FEAT-059/LAB-088/REF-03)
"""

import json
import time
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.logic.override_parser import is_override_query, parse_override_with_resident, save_override_to_file
from src.v5.foyer.maintenance_sweeper import MaintenanceSweeper
from src.equipment.sensory_manager import SensoryManager


class TestOverrideSatelliteIntegration:
    @pytest.mark.asyncio
    async def test_full_override_pipeline(self, tmp_path):
        """Tests query detection -> resident parse -> atomic disk save."""
        turn = "[ME] Wait, GEM-0142 is wrong, rank should be 5 and synopsis needs an update."
        is_override, gem_id = is_override_query(turn)
        assert is_override is True
        assert gem_id == "GEM-0142"

        # Mock resident returning JSON
        mock_resident = MagicMock()
        mock_resident.think = AsyncMock(return_value='{"rank": 5, "synopsis": "Updated validation methodology"}')

        updates = await parse_override_with_resident(gem_id, turn, mock_resident)
        assert updates["rank"] == 5
        assert updates["synopsis"] == "Updated validation methodology"
        assert updates.get("title") is None

        # Atomic persistence
        overrides_file = tmp_path / "overrides.json"
        success = save_override_to_file(gem_id, updates, overrides_path=str(overrides_file))
        assert success is True

        # Read back from disk
        with open(overrides_file, "r") as f:
            data = json.load(f)
        assert data["overrides"]["GEM-0142"]["rank"] == 5
        assert data["overrides"]["GEM-0142"]["synopsis"] == "Updated validation methodology"


class TestMaintenanceSweeperIntegration:
    def test_prune_and_scavenge_pipeline(self):
        """Tests buffer pruning followed by heap scavenger execution."""
        pending_chunks = {
            "fresh_key": ["chunk1", "chunk2"],
            "stale_key": ["stale_chunk"],
        }
        chunk_timestamps = {
            "fresh_key": time.time(),
            "stale_key": time.time() - 45.0,  # 45s old
        }

        # Run TTL pruning
        purged = MaintenanceSweeper.prune_ttl_buffer(pending_chunks, chunk_timestamps, max_age_s=30.0)
        assert "stale_key" in purged
        assert "fresh_key" not in purged
        assert "stale_key" not in pending_chunks
        assert "fresh_key" in pending_chunks

        # Run heap scavenger
        collected = MaintenanceSweeper.run_heap_scavenger()
        assert isinstance(collected, int)
        assert collected >= 0

    def test_thermal_probe_integration(self, tmp_path):
        """Tests thermal zone reading with mock sysfs file."""
        zone_file = tmp_path / "temp"
        zone_file.write_text("79500\n")  # 79.5°C

        throttled, temp_c = MaintenanceSweeper.check_cpu_thermal_throttle(
            threshold_milli=78000,
            thermal_zones=[str(zone_file)]
        )
        assert throttled is True
        assert temp_c == pytest.approx(79.5, rel=1e-2)


class TestAudioPipelineSensoryIntegration:
    def test_sensory_manager_audio_pipeline_chunking(self):
        """Tests SensoryManager streaming and buffer slicing via AudioPipeline."""
        broadcast_mock = AsyncMock()
        manager = SensoryManager(broadcast_mock)

        # Send 16000 samples (32000 bytes) of PCM data (below 24000 window)
        samples = np.ones(16000, dtype=np.int16) * 1000
        raw_bytes = samples.tobytes()

        result = manager.process_binary_chunk(raw_bytes)
        assert result is None  # No window extracted yet
        assert len(manager.audio_buffer) == 16000

        # Send another 16000 samples (total buffer = 32000 >= 24000)
        manager.process_binary_chunk(raw_bytes)
        # Sliced 24000 window, advanced by 16000 stride -> remaining buffer is 16000 samples
        assert len(manager.audio_buffer) == 16000
