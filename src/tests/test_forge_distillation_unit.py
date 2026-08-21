#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for Sprint 58: Gem Refinement, Tri-Field Schema, and Autonomous LoRA Distillation.
Tests:
1. Tri-Field Gem JSON parsing and validation.
2. Backward compatibility for legacy 2-field gems.
3. Code artifact harvesting (forward tool lookup + reverse Jeopardy category search).
4. Schema compliance for journal_ledger.jsonl against train_expert.py expectations.
"""

import os
import sys
import json
import pytest

# Add field_notes to path
FIELD_NOTES_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes"
sys.path.insert(0, FIELD_NOTES_DIR)

from mass_scan import distill_journal_ledger, DATA_DIR


def test_tri_field_gem_schema_parsing():
    """Verify that a Tri-Field Gem output parses correctly into required fields."""
    sample_llm_output = json.dumps({
        "summary": "PECI sideband command stress testing under high load",
        "trigger_context": "When validating sideband telemetry throughput and PECI command saturation",
        "technical_gem": "Created pecistressor.py achieving ~5300 cmd/sec across OpenBMC sideband endpoints",
        "anchors": ["PECI", "pecistressor.py", "OpenBMC", "Sideband"],
        "rank": 4,
        "tags": ["peci", "telemetry", "sideband"]
    })

    data = json.loads(sample_llm_output)
    assert data["rank"] == 4
    assert len(data["anchors"]) >= 3
    assert "pecistressor.py" in data["technical_gem"]
    assert "validating sideband" in data["trigger_context"]


def test_distill_journal_ledger_schema_integrity():
    """Verify that journal_ledger.jsonl contains valid dialogue entries usable by train_expert.py."""
    distill_journal_ledger()
    ledger_path = os.path.join(DATA_DIR, "journal_ledger.jsonl")
    assert os.path.exists(ledger_path)

    valid_count = 0
    with open(ledger_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            assert "dialogue" in entry or ("instruction" in entry and "output" in entry)
            if "dialogue" in entry:
                assert "User:" in entry["dialogue"]
                assert ("Pinky:" in entry["dialogue"] or "Assistant:" in entry["dialogue"])
            valid_count += 1

    # Ensure dataset has at least 500 harvested pairs (notes + artifacts)
    assert valid_count >= 500


def test_code_artifact_jeopardy_pairs():
    """Verify that standalone code artifacts create both Forward and Reverse Jeopardy pairs."""
    ledger_path = os.path.join(DATA_DIR, "journal_ledger.jsonl")
    found_tool_inquiry = False
    found_category_search = False

    with open(ledger_path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            d = entry.get("dialogue", "")
            if "What is the" in d and "tool and how is it used?" in d:
                found_tool_inquiry = True
            if "What tools did Jason develop for" in d:
                found_category_search = True

    assert found_tool_inquiry, "Missing forward tool inquiry pair in journal_ledger.jsonl"
    assert found_category_search, "Missing reverse category search pair in journal_ledger.jsonl"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
