"""
[STORY 70.11] Unit tests for the Sanitized Public Benchmark Exporter.

Verifies that LAN IPs, session tokens, and absolute paths are stripped from
the exported public_benchmarks.json artifact.
"""
import json
import os
import sys

import pytest

# Make the exporter importable regardless of CWD.
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "Portfolio_Dev",
        "field_notes",
    ),
)

from export_public_benchmarks import (  # noqa: E402
    ABS_PATH_RE,
    LAN_IP_RE,
    SESSION_TOKEN_RE,
    export,
    sanitize_text,
    sanitize_value,
)

LAN_IP = "192.168.1.26"
SESSION_TOKEN = "ses_65E082E7abc123"
ABS_PATH = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"


@pytest.fixture()
def sample_records():
    """Telemetry-shaped records containing every sensitive token type."""
    return [
        {
            "node": LAN_IP,
            "session": SESSION_TOKEN,
            "cmd": f"{ABS_PATH} --model /spe/models/llama32",
            "top": [{"pid": 1, "cmd": ABS_PATH}],
            "note": f"talked to {LAN_IP} using {SESSION_TOKEN}",
            "nested": {"deep": ABS_PATH},
            "safe": "keep me",
            "count": 42,
        }
    ]


def test_sanitize_text_redacts_all_tokens():
    text = f"ip={LAN_IP} ses={SESSION_TOKEN} path={ABS_PATH}"
    out = sanitize_text(text)
    assert LAN_IP not in out
    assert SESSION_TOKEN not in out
    assert ABS_PATH not in out
    assert "REDACTED_IP" in out
    assert "REDACTED_SESSION" in out
    assert "REDACTED_PATH" in out


def test_sanitize_value_recurses_into_nested_structures(sample_records):
    clean = sanitize_value(sample_records[0])
    assert LAN_IP not in json.dumps(clean)
    assert SESSION_TOKEN not in json.dumps(clean)
    assert ABS_PATH not in json.dumps(clean)
    assert clean["safe"] == "keep me"
    assert clean["count"] == 42
    assert clean["nested"]["deep"] == "REDACTED_PATH"


def test_regex_patterns_match_fixture_tokens():
    assert LAN_IP_RE.search(LAN_IP)
    assert SESSION_TOKEN_RE.search(SESSION_TOKEN)
    assert ABS_PATH_RE.search(ABS_PATH)


def test_export_writes_sanitized_public_benchmarks(tmp_path, monkeypatch, sample_records):
    import export_public_benchmarks as mod

    monkeypatch.setattr(mod, "OUTPUT_FILE", os.path.join(str(tmp_path), "public_benchmarks.json"))
    path = export(sample_records)

    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)

    assert "benchmarks" in payload
    serialized = json.dumps(payload)
    assert LAN_IP not in serialized
    assert SESSION_TOKEN not in serialized
    assert ABS_PATH not in serialized
    assert payload["benchmarks"][0]["safe"] == "keep me"
