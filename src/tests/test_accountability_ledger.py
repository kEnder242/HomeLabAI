# [Story 971 / FEAT-619 evolution] Single-Home Runtime Data & Interleaved Ledger Tests
# Verifies the watchdog writes ONLY to the canonical field_notes/data home and
# appends one flat JSONL line per audit run to accountability_ledger.jsonl.
import json
from unittest.mock import patch

import infra.standalone_accountability_watchdog as safw


class _stack:
    """Context manager that nests any number of patch() objects."""

    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        for p in reversed(self._patches):
            p.stop()
        return False


ALL_CHECKS = [
    "check_gpu_power_clamp",
    "check_foyer_and_vram",
    "check_stale_locks",
    "check_nightly_forge_liveness",
    "check_lora_training",
    "check_subconscious_dreaming",
]


def _check(name, passed):
    return {"name": name, "passed": passed, "detail": "OK" if passed else "Bad"}


def _mock_checks():
    patches = [
        patch.object(safw, n, return_value=_check(n, True)) for n in ALL_CHECKS
    ]
    return ["infra.standalone_accountability_watchdog.check_morning_round_table"] + [
        p for p in patches
    ]


def test_single_home_no_www_constant():
    """The www_deploy mirror target must be gone from the watchdog module."""
    assert not hasattr(safw, "WWW_DEPLOY_DIR")


def test_audit_writes_ledger_to_single_home_only(tmp_path):
    """audit_and_emit_digest must write digest + ledger into OUTPUT_DIR and
    nowhere else (no www_deploy twin)."""
    out = tmp_path / "field_notes" / "data"
    mocks = [patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", out)]
    for n in ALL_CHECKS:
        mocks.append(patch.object(safw, n, return_value=_check(n, True)))
    mocks.append(
        patch("infra.standalone_accountability_watchdog.check_morning_round_table",
              return_value=_check("probe", True))
    )
    with _stack(mocks):
        digest = safw.audit_and_emit_digest(run_live_probe=False)
    assert digest["overall_status"] == "PASS"
    assert (out / "daily_accountability_digest.json").exists()
    ledger = out / "accountability_ledger.jsonl"
    assert ledger.exists()
    lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["timestamp"] == digest["timestamp"]
    assert entry["overall_status"] == "PASS"
    assert entry["passed_checks"] == 7
    assert entry["total_checks"] == 7
    assert entry["discrepancies"] == []
    # The old www_deploy twin must NOT be created
    assert not (tmp_path / "www_deploy").exists()


def test_ledger_format_and_append_accumulates(tmp_path):
    """append_accountability_ledger emits exactly the 5 spec fields, one line per
    run, and successive runs accumulate (interleaved history, never truncated)."""
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path):
        d1 = {"timestamp": "2026-10-02T06:00:00+00:00", "overall_status": "PASS",
              "passed_checks": 7, "total_checks": 7, "discrepancies": []}
        d2 = {"timestamp": "2026-10-03T06:00:00+00:00", "overall_status": "DEGRADED",
              "passed_checks": 6, "total_checks": 7,
              "discrepancies": ["Power limit 170.1W exceeds 170.0W threshold"]}
        safw.append_accountability_ledger(d1)
        safw.append_accountability_ledger(d2)
        ledger = tmp_path / "accountability_ledger.jsonl"
        assert ledger.exists()
        lines = ledger.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        for line, expected in zip(lines, (d1, d2)):
            parsed = json.loads(line)
            assert set(parsed.keys()) == {
                "timestamp", "overall_status", "passed_checks", "total_checks", "discrepancies"
            }
            assert parsed == {
                "timestamp": expected["timestamp"],
                "overall_status": expected["overall_status"],
                "passed_checks": expected["passed_checks"],
                "total_checks": expected["total_checks"],
                "discrepancies": expected["discrepancies"],
            }
        # line 1 must be parseable standalone (JSONL contract for the poller)
        assert json.loads(lines[1])["overall_status"] == "DEGRADED"


def test_ledger_rotation_preserves_history(tmp_path):
    """When the ledger exceeds LEDGER_MAX_BYTES it rotates to .jsonl.1 instead of
    truncating, keeping the tail intact for the static site poller."""
    with patch("infra.standalone_accountability_watchdog.OUTPUT_DIR", tmp_path):
        ledger = tmp_path / "accountability_ledger.jsonl"
        old_line = {"timestamp": "2026-09-01T06:00:00", "overall_status": "PASS",
                    "passed_checks": 7, "total_checks": 7, "discrepancies": []}
        ledger.write_text(
            json.dumps(old_line) + "\n"
            + "x" * (safw.LEDGER_MAX_BYTES),  # push past the rotation threshold
            encoding="utf-8",
        )
        new_line = {"timestamp": "2026-10-02T06:00:00", "overall_status": "FAIL",
                    "passed_checks": 2, "total_checks": 7, "discrepancies": ["critical"]}
        safw.append_accountability_ledger(new_line)
    rotated = tmp_path / "accountability_ledger.jsonl.1"
    assert rotated.exists()
    assert rotated.read_text(encoding="utf-8").startswith(json.dumps(old_line))
    fresh = (tmp_path / "accountability_ledger.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(fresh) == new_line
