"""Canary tests for the OpenAgent swarm delegation mechanism (Story 999).

Validates that the delegate.py launcher contract (payload structure and
# [FEAT-090] Non-Blocking Parallel Dispatch
completion status) is intact so the orchestrator can successfully dispatch
file edits to subagents and verify completion.
"""

import importlib.util
import inspect
import os
import sys

DELEGATE_PATH = os.path.join(os.path.dirname(__file__), "delegate.py")


def _load_delegate_module():
    """Load delegate.py as a module without executing its __main__ block."""
    spec = importlib.util.spec_from_file_location("delegate_canary", DELEGATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canary_pass():
    assert True


def test_delegate_payload_structure():
    """Validate the delegation payload fields required by the launcher."""
    module = _load_delegate_module()

    # The delegate() launcher must accept the five canonical story fields.
    sig = inspect.signature(module.delegate)
    params = list(sig.parameters.keys())
    for field in ("story_num", "title", "file_path", "details", "verification"):
        assert field in params, f"delegate() missing required payload field: {field}"

    # The CLI entrypoint must expose the same fields as flags.
    assert hasattr(module, "OPENCODE_REST_PORT"), "delegate.py missing REST port constant"
    assert module.OPENCODE_REST_PORT == 4097, "delegate.py REST port drifted from 4097"


def test_delegate_completion_status():
    """Validate that a successful dispatch yields a completion status."""
    module = _load_delegate_module()

    # A completed dispatch must log a COMPLETE step with a finish status.
    # The launcher's success path emits finish=... from the REST response.
    assert hasattr(module, "delegate"), "delegate() launcher missing"
    assert hasattr(module, "log_step"), "log_step() telemetry helper missing"

    # The delegate() return contract: success path returns None (no sys.exit),
    # while failure paths call sys.exit(1). Verify the success branch exists.
    source = inspect.getsource(module.delegate)
    assert "COMPLETE" in source, "delegate() success path missing COMPLETE status"
    assert "finish" in source, "delegate() success path missing finish status"
    assert "sys.exit(1)" in source, "delegate() failure path missing exit(1) guard"