"""Unit tests for OpsRunner [FEAT-620]."""

import pytest
from ops.ops_runner import OpsRunner, execute_op


def test_ops_runner_vitals():
    """Verify get_gpu_vitals returns structured telemetry."""
    runner = OpsRunner()
    res = runner.get_gpu_vitals()
    assert "status" in res
    if res["status"] == "SUCCESS":
        assert "temp_c" in res
        assert "vram_used_mb" in res
        assert "vram_total_mb" in res


def test_ops_runner_purge_cuda_cache():
    """Verify purge_cuda_cache executes without exception."""
    runner = OpsRunner()
    res = runner.purge_cuda_cache()
    assert res["status"] == "SUCCESS"
    assert "vram_mb" in res


def test_execute_op_unknown_action():
    """Verify unknown action returns structured error."""
    res = execute_op("invalid_action_xyz")
    assert res["status"] == "ERROR"
    assert "Unknown action" in res["error"]
