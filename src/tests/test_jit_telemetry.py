"""
[Story 100.5 / FEAT-649] Sub-Inference Observability & Blended Swarm Telemetry Tests.

Validates that:
1. M5 Air neural map-reduce appends structured receipts to .jit_cache/sub_inference_ledger.jsonl.
2. delegate.py:aggregate_sub_inference_tokens reads and sums un-tallied receipts.
3. delegate.py:record_swarm_telemetry blends sub-inference tokens into outer story tokens.
"""

import json
import os
import time
import pytest

from v5.cognition.context_prewarmer import (
    record_sub_inference_receipt,
    SUB_INFERENCE_LEDGER_PATH,
)
from tests.delegate import (
    aggregate_sub_inference_tokens,
    record_swarm_telemetry,
)


def test_sub_inference_receipt_logging(tmp_path):
    """Assert record_sub_inference_receipt writes valid structured JSONL."""
    test_file = "src/v5/cognition/test_sample.py"
    t0 = time.time() - 1.0

    record_sub_inference_receipt(
        engine="m5_air",
        file_path=test_file,
        prompt_tokens=420,
        completion_tokens=69,
    )

    assert os.path.exists(SUB_INFERENCE_LEDGER_PATH)

    # Ingest and verify
    sub_inf = aggregate_sub_inference_tokens(since_timestamp=t0)
    assert sub_inf["prompt_tokens"] >= 420
    assert sub_inf["completion_tokens"] >= 69
    assert sub_inf["total_tokens"] >= 489
    assert sub_inf["entries_count"] >= 1


def test_record_swarm_telemetry_blending():
    """Assert record_swarm_telemetry blends sub-inference tokens into outer tokens dictionary."""
    t0 = time.time()
    test_file = "src/v5/cognition/blended_sample.py"

    # Log a known receipt
    record_sub_inference_receipt(
        engine="m5_air",
        file_path=test_file,
        prompt_tokens=300,
        completion_tokens=50,
    )

    tokens = {"input": 1000, "output": 200, "total": 1200}
    model_obj = {"providerID": "my-windows-4090", "modelID": "Qwen3.8-27B-GGUF"}

    record_swarm_telemetry(
        story_num=100,
        sprint_num=100,
        title="Test Blended Telemetry",
        model_obj=model_obj,
        duration=5.0,
        tokens=tokens,
        text_len=800,
        start_time=t0,
    )

    assert "sub_inference" in tokens
    assert tokens["sub_inference"]["total_tokens"] >= 350
    assert tokens["blended_total"] >= 1550
