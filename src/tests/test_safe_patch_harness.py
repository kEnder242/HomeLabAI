"""
[FEAT-529] Verification Suite: Safe-Patch Subagent Certification Harness
Asserts that patch_target.py was modified surgically by the subagent to include
calculate_energy_efficiency() without breaking existing AST functions.
"""
import ast
import inspect
from tests.fixtures import patch_target


def test_existing_patch_target_functions():
    """Verify original baseline functions are preserved."""
    metrics = patch_target.compute_telemetry_metrics(tokens=100, duration_s=2.0)
    assert metrics["throughput_tok_s"] == 50.0
    assert metrics["duration_s"] == 2.0

    badge = patch_target.format_node_badge("m5_air", tier="local")
    assert badge == "[LOCAL] M5_AIR"


def test_safe_patch_new_function():
    """Verify calculate_energy_efficiency was added surgically via safe_patch."""
    assert hasattr(patch_target, "calculate_energy_efficiency"), (
        "Expected patch_target.py to have calculate_energy_efficiency function added by subagent"
    )

    fn = getattr(patch_target, "calculate_energy_efficiency")
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    assert "tokens" in params and "duration_s" in params and "watts" in params, (
        f"Expected parameters (tokens, duration_s, watts), got {params}"
    )

    # Test calculation: 100 tokens in 2s (50 tok/s) at 25W = 2.0 tokens/joule
    res = fn(tokens=100, duration_s=2.0, watts=25.0)
    assert res == 2.0 or (isinstance(res, dict) and res.get("tokens_per_joule") == 2.0), (
        f"Expected 2.0 tokens/joule, got {res}"
    )


def test_patch_target_ast_integrity():
    """Verify the file has valid AST syntax with all 3 functions present."""
    from pathlib import Path
    target_path = Path(__file__).resolve().parent / "fixtures" / "patch_target.py"
    with open(target_path, "r") as f:
        tree = ast.parse(f.read())

    func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert "compute_telemetry_metrics" in func_names
    assert "format_node_badge" in func_names
    assert "calculate_energy_efficiency" in func_names
