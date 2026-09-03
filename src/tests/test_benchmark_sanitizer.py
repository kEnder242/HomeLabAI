"""
[FEAT-527] Verification Suite for Story 70.11 Sanitized Public Benchmark Exporter
Validates that export_public_benchmarks.py strips LAN IPs, session tokens, and local paths.
"""
import json
import pytest
from pathlib import Path
import sys

# Add Portfolio_Dev/field_notes to sys.path
portfolio_fn = Path(__file__).resolve().parent.parent.parent.parent / "Portfolio_Dev" / "field_notes"
sys.path.insert(0, str(portfolio_fn))

import export_public_benchmarks as exp


def test_sanitize_text_redactions():
    """Verify regex redactor catches private LAN IPs, session tokens, and absolute paths."""
    sample = "Host 192.168.1.26 executed session ses_f9a1780cfffe1bNQmYOUEcG7M1 at /home/jallred/Dev_Lab/secret.py"
    sanitized = exp.sanitize_text(sample)

    assert "192.168.1.26" not in sanitized
    assert exp.LAN_REDACTED in sanitized

    assert "ses_f9a1780cfffe1bNQmYOUEcG7M1" not in sanitized
    assert exp.SESSION_REDACTED in sanitized

    assert "/home/jallred" not in sanitized
    assert exp.PATH_REDACTED in sanitized


def test_export_structure():
    """Verify export() generates valid JSON with required benchmark bundle keys."""
    test_records = [
        {
            "seat": "Apple M5 Air",
            "model": "mlx-community--Qwen3.8-27B-4bit",
            "throughput_tok_s": 35.4,
            "ttft_ms": 320,
            "ip": "192.168.1.46",
            "session_id": "ses_abc12345",
            "path": "/home/jallred/Dev_Lab/benchmarks.js"
        }
    ]
    out_path = exp.export(test_records)
    assert Path(out_path).exists()

    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "benchmarks" in data
    assert len(data["benchmarks"]) == 1
    bm = data["benchmarks"][0]
    assert bm["ip"] == exp.LAN_REDACTED
    assert bm["session_id"] == exp.SESSION_REDACTED
    assert bm["path"] == exp.PATH_REDACTED
    assert bm["throughput_tok_s"] == 35.4
