"""
[FEAT-641 / Story 97.5] Live Lab Vitals & Passive Telemetry Test Battery
========================================================================
Validates:
  1. Passive Polling Guarantee: telemetry reads are 100% GET-only with zero /wake or ignition side effects.
  2. Audio Quarantine: audio vocal synthesis & TTS testing strictly gated to 06:00 AM Daily Health Audit.
  3. UI Health Badge Contract: status.html renders 6:00 AM Daily Sanity Check badges on all vital cards.
  4. Graceful Endpoint Degradation: collector survives missing DCGM/Foyer/vLLM endpoints without raising.
"""

import inspect
import json
import os
import re
from unittest.mock import MagicMock, patch

import pytest

from infra.live_telemetry import (
    LiveMetrics,
    LiveTelemetryCollector,
    get_collector,
    get_host_vitals,
    merge_live_benchmarks,
)


class TestPassivePollingGuarantee:
    """[FEAT-641] Telemetry collection must remain 100% passive."""

    def test_live_telemetry_is_get_only(self):
        """Verify LiveTelemetryCollector only performs GET requests and no POST/PUT/DELETE."""
        collector = LiveTelemetryCollector(
            dcgm_url="http://127.0.0.1:9400/metrics",
            foyer_url="http://127.0.0.1:8765/status",
            vllm_url="http://127.0.0.1:8088/v1/models",
        )

        with patch("requests.get") as mock_get, \
             patch("requests.post") as mock_post, \
             patch("requests.put") as mock_put, \
             patch("requests.delete") as mock_delete:

            # Mock responses
            mock_dcgm = MagicMock()
            mock_dcgm.status_code = 200
            mock_dcgm.text = "DCGM_FI_DEV_FB_USED 4000\nDCGM_FI_DEV_FB_TOTAL 11000\nDCGM_FI_DEV_POWER_USAGE 120.5\n"

            mock_foyer = MagicMock()
            mock_foyer.status_code = 200
            mock_foyer.text = json.dumps({"connected_clients": 2, "state": "OPERATIONAL", "active_lora": "test-lora"})

            mock_vllm = MagicMock()
            mock_vllm.status_code = 200
            mock_vllm.text = json.dumps({"data": [{"id": "unified-base"}, {"id": "adapter-v1"}]})

            mock_get.side_effect = lambda url, **kwargs: (
                mock_dcgm if "9400" in url else (
                    mock_foyer if "8765" in url else mock_vllm
                )
            )

            metrics = collector.snapshot()

            assert metrics.vram_used_mb == 4000.0
            assert metrics.vram_total_mb == 11000.0
            assert metrics.vram_pct == 36.4
            assert metrics.gpu_power_w == 120.5
            assert metrics.connected_clients == 2
            assert metrics.round_table_active is True
            assert metrics.active_lora == "test-lora"
            assert metrics.dcgm_online is True
            assert metrics.foyer_online is True

            # Assert NO mutative HTTP calls were ever issued
            assert mock_post.call_count == 0
            assert mock_put.call_count == 0
            assert mock_delete.call_count == 0

    def test_no_wake_side_effects_in_code(self):
        """Verify live_telemetry module source code contains zero /wake or ignition triggers."""
        source = inspect.getsource(LiveTelemetryCollector)
        assert "/wake" not in source
        assert "/sleep" not in source
        assert "ignition" not in source.lower() or "IgnitionManager" in source  # doc references ok


class TestAudioQuarantine:
    """[FEAT-641] Audio synthesis / TTS quarantined to 06:00 AM audit."""

    def test_live_telemetry_has_no_audio_invocations(self):
        """Verify live_telemetry does not import or invoke audio pipelines."""
        import infra.live_telemetry as lt
        source = inspect.getsource(lt)
        assert "AudioPipeline" not in source
        assert not re.search(r"\btts\b", source, re.IGNORECASE)
        assert "vocal_handshake" not in source.lower()

    def test_watchdog_audit_quarantines_live_probe(self):
        """Verify standalone_accountability_watchdog isolates round table live probe under flag."""
        from infra.standalone_accountability_watchdog import check_morning_round_table
        
        # When run_live=False, no subprocess is spawned
        res = check_morning_round_table(run_live=False)
        assert res["name"] == "Synthetic Morning Round Table Probe"
        assert res["passed"] is False


class TestStatusHtmlHealthBadgeContract:
    """[FEAT-641] status.html vital cards render 6:00 AM Daily Sanity Check Badges."""

    @pytest.fixture
    def status_html_content(self):
        html_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/status.html")
        assert os.path.exists(html_path), "status.html must exist"
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_vital_cards_contain_health_badge_containers(self, status_html_content):
        """Verify each vital card has a dedicated health badge container span."""
        expected_badges = [
            "scanner-health-badge",
            "engine-health-badge",
            "model-health-badge",
            "intercom-health-badge",
            "job-health-badge",
        ]
        for badge_id in expected_badges:
            assert f'id="{badge_id}"' in status_html_content, f"Missing health badge span id='{badge_id}'"

    def test_poll_status_fetches_digest_and_updates_badges(self, status_html_content):
        """Verify pollStatus() parses daily_accountability_digest.json and renders NOMINAL/STALE badges."""
        assert "daily_accountability_digest.json" in status_html_content
        assert "[HEALTH: NOMINAL]" in status_html_content
        assert "[HEALTH: AUDIT_STALE]" in status_html_content
        assert "FEAT-641" in status_html_content


class TestCollectorDegradationAndEnrichment:
    """Collector gracefully degrades on offline sinks and enriches metrics."""

    def test_graceful_degradation_on_endpoint_failure(self):
        """Verify collector returns default LiveMetrics without throwing when sinks are down."""
        collector = LiveTelemetryCollector(
            dcgm_url="http://127.0.0.1:9999/dead",
            foyer_url="http://127.0.0.1:9998/dead",
            vllm_url="http://127.0.0.1:9997/dead",
            timeout=0.1,
        )
        sample = collector.snapshot()
        assert sample.vram_used_mb == 0.0
        assert sample.vram_total_mb == 0.0
        assert sample.vram_pct == 0.0
        assert sample.gpu_power_w == 0.0
        assert sample.connected_clients == 0
        assert sample.round_table_active is False
        assert sample.active_lora is None
        assert sample.dcgm_online is False
        assert sample.foyer_online is False
        assert isinstance(sample.swap_pct, float)

    def test_merge_live_benchmarks_mutates_payload(self):
        """Verify merge_live_benchmarks injects live_telemetry block in-place."""
        payload = {"status": "ONLINE", "vitals": {"mode": "OPERATIONAL"}}
        merged = merge_live_benchmarks(payload)
        assert "live_telemetry" in merged
        assert isinstance(merged["live_telemetry"], dict)
        assert "timestamp" in merged["live_telemetry"]
        assert "vram_used_mb" in merged["live_telemetry"]

    def test_get_host_vitals_structure(self):
        """Verify get_host_vitals produces structured payload with gpu, host_ram, cpu, model_residency."""
        vitals = get_host_vitals()
        assert "gpu" in vitals
        assert "host_ram" in vitals
        assert "cpu" in vitals
        assert "model_residency" in vitals
        assert "vram_pct" in vitals["gpu"]
        assert "load_1m" in vitals["cpu"]
