"""
[Story 100.6 / FEAT-649] Greenfield Shakedown Test File.
This file is the target for Sprint 100 Story 100.6 live shakedown.
"""

def shakedown_target_fn() -> str:
    """Target function for JIT safe_patch verification."""
    return "CERTIFIED_JIT_V1"


def test_shakedown_target_fn():
    """Verify shakedown target function returns certified value."""
    val = shakedown_target_fn()
    assert val == "CERTIFIED_JIT_V1"
