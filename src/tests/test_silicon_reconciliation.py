"""[STORY 99.3] Silicon Reconciliation on /reload_residents - hermetic unit tests."""
import ast
import importlib
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(TESTS_DIR, ".."))
ROUTER_PATH = os.path.join(SRC_DIR, "v5", "foyer", "router.py")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _handler_node():
    with open(ROUTER_PATH) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "handle_reload_residents":
            return node
    raise AssertionError("handle_reload_residents not found in router.py")


def _reload_calls():
    calls = []
    for sub in ast.walk(_handler_node()):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "reload"
            and sub.args
        ):
            calls.append((sub.lineno, ast.unparse(sub.args[0]).strip()))
    return calls


class TestSiliconReconciliation:
    def test_triage_reconciles_before_cognitive_hub(self):
        order = {name: ln for ln, name in _reload_calls()}
        assert "logic.speculative_triage" in order, "speculative_triage reload missing"
        assert "logic.cognitive_hub" in order, "cognitive_hub reload missing"
        assert order["logic.speculative_triage"] < order["logic.cognitive_hub"], (
            "speculative_triage must reload BEFORE cognitive_hub"
        )

    def test_success_payload_flags_reconciled_silicon(self):
        for sub in ast.walk(_handler_node()):
            if isinstance(sub, ast.Dict):
                keys = {k.value for k in sub.keys if isinstance(k, ast.Constant)}
                if "reconciled_silicon" in keys:
                    val = sub.values[list(sub.keys).index(
                        next(k for k in sub.keys if isinstance(k, ast.Constant) and k.value == "reconciled_silicon"))]
                    assert isinstance(val, ast.Constant) and val.value is True
                    return
        raise AssertionError("reconciled_silicon key not found in success payload")

    def test_reconciliation_log_message(self):
        with open(ROUTER_PATH) as f:
            assert "[FOYER] Silicon topology and cognitive modules reconciled." in f.read()

    def test_reload_refreshes_module_level_state(self):
        import logic.speculative_triage as st
        st._SILICON_RECONCILE_SENTINEL = "stale"
        importlib.reload(st)
        assert not hasattr(st, "_SILICON_RECONCILE_SENTINEL"), "module-level state must reset on reload"
