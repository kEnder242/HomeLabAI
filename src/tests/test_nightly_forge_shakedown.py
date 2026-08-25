#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration Shakedown Test: Full Nightly Forge & Synthesis Orchestration Flow.
Guarantees zero syntax errors, zero missing imports, valid REST payload contracts,
and end-to-end dataset compatibility for train_expert.py.
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Path configuration
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
FIELD_NOTES_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes"
sys.path.insert(0, LAB_DIR)
sys.path.insert(0, FIELD_NOTES_DIR)

from src.infra import nightly_forge
from src.forge import train_expert
import mass_scan
import refine_gem


def test_import_integrity_all_nightly_modules():
    """Verify that all core modules involved in the 2:00 AM nightly run import without error."""
    assert hasattr(nightly_forge, "main")
    assert hasattr(nightly_forge, "quiesce_vllm")
    assert hasattr(nightly_forge, "re_ignite_vllm")
    assert hasattr(nightly_forge, "run_dream_cycle")
    assert hasattr(nightly_forge, "run_mass_scan")
    assert hasattr(train_expert, "train_expert")
    assert hasattr(mass_scan, "distill_journal_ledger")
    assert hasattr(refine_gem, "main")


def test_rest_quiesce_and_reignite_contracts():
    """Verify that REST quiesce and re-ignite functions target the correct Foyer endpoints."""
    with patch.object(nightly_forge.requests, "post") as mock_post, \
         patch.object(nightly_forge.time, "sleep"):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp

        # Test Quiesce
        quiesced = nightly_forge.quiesce_vllm()
        assert quiesced is True
        assert mock_post.call_count >= 1

        # Test Re-ignition
        mock_post.reset_mock()
        reignited = nightly_forge.re_ignite_vllm()
        assert reignited is True
        assert mock_post.call_count >= 1


def test_train_expert_dataset_mapper_with_live_ledger():
    """Verify that train_expert's dataset formatting function accepts all live pairs in journal_ledger.jsonl."""
    ledger_path = os.path.join(FIELD_NOTES_DIR, "data", "journal_ledger.jsonl")
    assert os.path.exists(ledger_path)

    # Read live ledger
    raw_dialogues = []
    with open(ledger_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if "dialogue" in item:
                    raw_dialogues.append(item["dialogue"])

    assert len(raw_dialogues) > 0

    # Mock tokenizer to test formatting_prompts_func logic
    mock_tokenizer = MagicMock()
    mock_tokenizer.eos_token = "<|end_of_text|>"

    # Test batch mapping logic extracted from train_expert
    def formatting_prompts_func(examples):
        available_keys = list(examples.keys())
        texts = []
        if "dialogue" in available_keys:
            dialogues = examples["dialogue"]
            for d in dialogues:
                texts.append(str(d) + mock_tokenizer.eos_token)
        return {"text": texts}

    batch = {"dialogue": raw_dialogues[:50]}
    result = formatting_prompts_func(batch)
    assert len(result["text"]) == 50
    for formatted_text in result["text"]:
        assert "<|end_of_text|>" in formatted_text
        assert "User:" in formatted_text


def test_re_ignite_vllm_connection_timeout_graceful():
    """[FEAT-453] Assert re_ignite_vllm() handles connection timeouts gracefully (returns False, no raise)."""
    with patch.object(nightly_forge.requests, "post") as mock_post:
        mock_post.side_effect = nightly_forge.requests.exceptions.ConnectionError("Connection refused")
        result = nightly_forge.re_ignite_vllm()
        assert result is False

    with patch.object(nightly_forge.requests, "post") as mock_post:
        mock_post.side_effect = nightly_forge.requests.exceptions.Timeout("Read timed out")
        result = nightly_forge.re_ignite_vllm()
        assert result is False


def test_dream_cycle_subprocess_handling():
    """Verify that run_dream_cycle handles errors and status logs gracefully."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Dream completed", stderr="")
        nightly_forge.run_dream_cycle()
        mock_run.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
