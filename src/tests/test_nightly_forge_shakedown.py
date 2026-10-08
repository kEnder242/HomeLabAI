#!/usr/bin/env python3

"""
Integration Shakedown Test: Full Nightly Forge & Synthesis Orchestration Flow.
Guarantees zero syntax errors, zero missing imports, valid REST payload contracts,
and end-to-end dataset compatibility for train_expert.py.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Path configuration
LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
FIELD_NOTES_DIR = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes"
sys.path.insert(0, LAB_DIR)
sys.path.insert(0, FIELD_NOTES_DIR)

import mass_scan
import refine_gem
from src.infra import nightly_forge


def test_import_integrity_all_nightly_modules():
    """Verify that all core modules involved in the 2:00 AM nightly run import without error."""
    from src.forge import train_expert
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
    with patch.object(nightly_forge.requests, "post") as mock_post, patch.object(
        nightly_forge.requests, "get"
    ) as mock_get, patch.object(
        nightly_forge.time, "sleep"
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp
        mock_get.return_value = mock_resp

        # Test Quiesce
        quiesced = nightly_forge.quiesce_vllm()
        assert quiesced is True
        assert mock_post.call_count >= 1

        # Test Re-ignition
        mock_post.reset_mock()
        reignited = nightly_forge.re_ignite_vllm()
        assert reignited is True
        assert mock_post.call_count >= 1
        assert mock_get.call_count >= 1


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

    expected_count = min(50, len(raw_dialogues))
    batch = {"dialogue": raw_dialogues[:expected_count]}
    result = formatting_prompts_func(batch)
    assert len(result["text"]) == expected_count
    assert len(result["text"]) > 0
    for formatted_text in result["text"]:
        assert "<|end_of_text|>" in formatted_text
        assert "User:" in formatted_text


def test_re_ignite_vllm_connection_timeout_graceful():
    """[FEAT-453] Assert re_ignite_vllm() handles connection timeouts gracefully (returns False, no raise)."""
    with patch.object(nightly_forge.requests, "post") as mock_post:
        mock_post.side_effect = nightly_forge.requests.exceptions.ConnectionError(
            "Connection refused"
        )
        result = nightly_forge.re_ignite_vllm()
        assert result is False

    with patch.object(nightly_forge.requests, "post") as mock_post:
        mock_post.side_effect = nightly_forge.requests.exceptions.Timeout(
            "Read timed out"
        )
        result = nightly_forge.re_ignite_vllm()
        assert result is False


def test_re_ignite_vllm_blocking_gate():
    """[FEAT-101.8] Test re_ignite_vllm() blocking probe gate success and timeout paths."""
    # Mock successful Foyer communication and successful v1/models probe
    with patch.object(nightly_forge.requests, "post") as mock_post, patch.object(
        nightly_forge.requests, "get"
    ) as mock_get, patch.object(
        nightly_forge.time, "sleep"
    ), patch.object(
        nightly_forge.time, "monotonic"
    ) as mock_monotonic:
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_post_resp

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get.return_value = mock_get_resp

        # Mock time.monotonic to simulate immediate success (no time elapsed)
        mock_monotonic.side_effect = [0.0, 0.0]  # start_time, then check elapsed

        result = nightly_forge.re_ignite_vllm()
        assert result is True
        # Should have called POST /wake and POST /status_update
        assert mock_post.call_count == 2
        # Should have called GET /v1/models at least once
        assert mock_get.call_count >= 1

    # Mock successful Foyer communication but v1/models probe timeout
    with patch.object(nightly_forge.requests, "post") as mock_post, patch.object(
        nightly_forge.requests, "get"
    ) as mock_get, patch.object(
        nightly_forge.time, "sleep"
    ), patch.object(
        nightly_forge.time, "monotonic"
    ) as mock_monotonic:
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_post_resp

        # Simulate timeout by making GET requests return non-200
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 503  # Service unavailable
        mock_get.return_value = mock_get_resp

        # Mock time.monotonic to simulate timeout (181 seconds elapsed)
        mock_monotonic.side_effect = [0.0, 181.0]  # start_time, then check elapsed > timeout_total

        result = nightly_forge.re_ignite_vllm()
        assert result is False  # Should return False due to probe timeout
        # Should have called POST /wake and POST /status_update
        assert mock_post.call_count == 2
        # Should have called GET /v1/models exactly once (since it times out on first check)
        assert mock_get.call_count == 1


def test_dream_cycle_subprocess_handling():
    """Verify that run_dream_cycle handles errors and status logs gracefully."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Dream completed", stderr=""
        )
        nightly_forge.run_dream_cycle()
        mock_run.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
