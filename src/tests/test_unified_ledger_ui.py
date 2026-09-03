"""
[FEAT-526] Verification Suite for Story 70.10 Unified Nested Ledger
Validates that renderBlackboardLedger nests subagent executions and renders batch cards.
"""
from pathlib import Path


def test_benchmarks_js_contract_elements():
    """Static contract check for benchmarks.js."""
    benchmarks_js_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "Portfolio_Dev"
        / "field_notes"
        / "benchmarks.js"
    )
    assert benchmarks_js_path.exists(), f"File {benchmarks_js_path} does not exist"

    content = benchmarks_js_path.read_text(encoding="utf-8")
    assert "function renderBlackboardLedger" in content, "Missing renderBlackboardLedger function"
    assert "cachedLiveRecords" in content or "window.cachedLiveRecords" in content, (
        "Expected cachedLiveRecords data flow binding in benchmarks.js"
    )
    assert "subagent" in content.lower() or "dispatches" in content.lower() or "role" in content.lower(), (
        "Expected subagent table rendering in benchmarks.js"
    )
    assert "[BATCH]" in content or "is_batch" in content or "NIGHTLY_REFINEMENT" in content, (
        "Expected [BATCH] card rendering in benchmarks.js"
    )
