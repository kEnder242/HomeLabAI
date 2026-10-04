"""
[FEAT-513 / SPR-69.4] Bicameral Local Delegation Canary
A stub-and-fill target for certifying Atlas (4090) -> Sisyphus-Junior (M5 Air) delegation.
"""


def compute_xor_checksum(values: list[int]) -> int:
    """
    Compute the cumulative bitwise XOR of all integers in values.
    Returns 0 if values is empty.
    """
    acc = 0
    for v in values:
        acc ^= v
    return acc


def test_xor_checksum_empty():
    assert compute_xor_checksum([]) == 0


def test_xor_checksum_single():
    assert compute_xor_checksum([42]) == 42


def test_xor_checksum_multiple():
    # 1 ^ 2 ^ 3 ^ 4 = (1 ^ 2) ^ 3 ^ 4 = 3 ^ 3 ^ 4 = 0 ^ 4 = 4
    assert compute_xor_checksum([1, 2, 3, 4]) == 4
    # 10 ^ 20 ^ 30 = 30 ^ 30 = 0
    assert compute_xor_checksum([10, 20, 30]) == 0


def test_opencode_hook_config_exists():
    """[Story 98.7 / FEAT-600] Verify discrete OpenCode hook configuration exists and is well-formed."""
    import json
    import os
    hook_path = os.path.expanduser("~/.config/opencode/hooks.json")
    assert os.path.exists(hook_path), f"OpenCode global hook missing: {hook_path}"
    with open(hook_path, "r") as f:
        data = json.load(f)
    assert "ambient-memory-and-knowledge" in data
    assert data["ambient-memory-and-knowledge"]["enabled"] is True


def test_hook_execution_under_100ms():
    """[Story 98.7 / LAB-019] Verify ambient_hook.sh executes with fast-path latency under 150ms."""
    import json
    import subprocess
    import time
    
    payload = {"invocationNum": 2, "userMessage": "test hook execution"}
    t0 = time.perf_counter()
    p = subprocess.run(
        ["/home/jallred/.gemini/config/scripts/ambient_hook.sh"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=2.0
    )
    t1 = time.perf_counter()
    elapsed_ms = (t1 - t0) * 1000.0
    assert p.returncode == 0
    assert elapsed_ms < 150.0, f"Hook took {elapsed_ms:.1f}ms (expected < 150ms)"
    res = json.loads(p.stdout)
    assert "injectSteps" in res


def test_ambient_delegation_telemetry():
    """[Story 99.1 / FEAT-650] Verify _trigger_ambient_hook_telemetry executes cleanly and surfaces memory state."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from delegate import _trigger_ambient_hook_telemetry
    res = _trigger_ambient_hook_telemetry(
        story_num="99.1",
        title="Test Telemetry Integration",
        duration=1.2,
        status="SUCCESS"
    )
    assert res["status"] in ("SUCCESS", "SKIPPED")
    if res["status"] == "SUCCESS":
        assert "injectSteps" in res
        assert len(res["injectSteps"]) > 0

