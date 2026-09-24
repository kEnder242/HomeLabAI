"""
[FEAT-607 / LAB-110] Unit Test: Nightly Accountability Evaluator & Green Lie Sentry
Tests evaluate_nightly_accountability against mock pass/degraded/fail telemetries.
"""
import pytest
import os
import json
import tempfile
from infra.nightly_forge import evaluate_nightly_accountability


def test_evaluate_nightly_accountability_pass():
    """Verify that a full 11-stage nominal telemetry payload returns PASS."""
    telemetry = {
        "gpu_power_clamped": True,
        "vram_quiesced": True,
        "lora_status": "COMPLETED",
        "adapters_trained": ["cli_voice_v1", "lab_history_v1", "triage_v1", "reviewer_v1"],
        "re_ignited": True,
        "dream_telemetry": {"status": "PASS", "turns_synthesized": 3, "items_refined": 1},
        "round_table_probe": {
            "status": "PASS",
            "greeting_latency_ms": 45.0,
            "circuit_latency_ms": 350.0,
            "critic_score": 0.95
        }
    }

    digest = evaluate_nightly_accountability(telemetry)
    assert digest["overall_status"] == "PASS"
    assert digest["passed_checks"] == digest["total_checks"]
    assert len(digest["discrepancies"]) == 0


def test_evaluate_nightly_accountability_zero_work_green_lie():
    """Verify BKM-062 Green Lie Detection: 0 dream turns and failed probe flags FAIL."""
    telemetry = {
        "gpu_power_clamped": True,
        "vram_quiesced": True,
        "lora_status": "COMPLETED",
        "adapters_trained": ["cli_voice_v1", "lab_history_v1", "triage_v1", "reviewer_v1"],
        "re_ignited": True,
        "dream_telemetry": {"status": "PASS", "turns_synthesized": 0, "items_refined": 0},  # Green Lie!
        "round_table_probe": {
            "status": "FAIL",
            "error": "Triage timeout"
        }
    }

    digest = evaluate_nightly_accountability(telemetry)
    assert digest["overall_status"] == "FAIL"
    assert len(digest["discrepancies"]) >= 2
    assert any("Green Lie" in d for d in digest["discrepancies"])
