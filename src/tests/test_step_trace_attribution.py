"""[FEAT-671 / LOOP-005 / BKM-035 / Story 108.15] Companion Unit Tests:
Interactive Step-Trace Root Cause Attribution & Negative Exemplar Flywheel.
"""
import json
import os
import tempfile
import time
import pytest
from unittest.mock import MagicMock, AsyncMock

from logic.cognitive_hub import CognitiveHub, record_negative_exemplar


def test_step_trace_detects_stage5_voice_drift_scaffolding():
    """Check 1: Pinky TL;DR containing prompt leaks ([BUDGET], STAGE_2, **) maps to STAGE_5_VOICE_DRIFT."""
    hub = CognitiveHub.__new__(CognitiveHub)
    artifacts = {
        "query": "What is the ESB2 firmware?",
        "dt_synthesis": "ESB2 firmware v2.1 was validated in 2016.",
        "pinky_tldr": "[BUDGET]: Headroom ceiling is 900 tokens. **TECHNICAL INTUITION**: Firmware is v2.1.",
        "vibe": "TECHNICAL",
        "candidate_count": 1,
        "kept_ids": [1],
    }
    result = hub.step_trace_attribution(artifacts, user_feedback="It leaked internal headers")
    assert result["defect_stage"] == "STAGE_5_VOICE_DRIFT"
    assert "leak" in result["reason"].lower()


def test_step_trace_detects_stage4_strategy_hallucination_on_audit_mismatch():
    """Check 2: Sovereign 27B entailment audit tagged MISMATCH maps to STAGE_4_HALLUCINATION."""
    hub = CognitiveHub.__new__(CognitiveHub)
    artifacts = {
        "query": "Did we run Kubernetes in 2012?",
        "bedrock_payload": "ESB2 board ran Linux 2.6 with Xen hypervisor in 2012.",
        "dt_synthesis": "Acme Lab deployed Kubernetes cluster on ESB2 in 2012 with 4 worker nodes.",
        "pinky_tldr": "Narf! We ran Kubernetes on the 2012 cluster with 4 worker nodes.",
        "audit": "CLAIM_CHECK: Kubernetes was released in 2014; archive mentions Xen only.\n\nVERDICT: MISMATCH",
        "vibe": "HISTORICAL",
        "candidate_count": 1,
        "kept_ids": [1],
    }
    result = hub.step_trace_attribution(artifacts, user_feedback="Kubernetes didn't exist in 2012, this is false")
    assert result["defect_stage"] == "STAGE_4_HALLUCINATION"
    assert "audit" in result["reason"].lower()


def test_step_trace_detects_stage3_false_drop():
    """Check 3: Brain gatekeeper dropped all candidate chunks resulting in 0/N Negative Moat."""
    hub = CognitiveHub.__new__(CognitiveHub)
    artifacts = {
        "query": "What was the package thermal limit on the ESB2 board?",
        "candidate_count": 2,
        "kept_ids": [],
        "drop_ids": [1, 2],
        "bedrock_payload": "",
        "dt_synthesis": "",
        "pinky_tldr": "Inform Jason playfully that no matching lab notes were found.",
        "vibe": "TECHNICAL",
    }
    result = hub.step_trace_attribution(artifacts, user_feedback="The thermal limit notes should have been kept")
    assert result["defect_stage"] == "STAGE_3_FALSE_DROP"
    assert "dropped all 2" in result["reason"].lower()


def test_step_trace_detects_stage2_retrieval_gap():
    """Check 4: ChromaDB returned 0 candidate chunks on a grounded technical inquiry."""
    hub = CognitiveHub.__new__(CognitiveHub)
    artifacts = {
        "query": "Explain PECI thermal margins on Aurora nodes",
        "candidate_count": 0,
        "kept_ids": [],
        "drop_ids": [],
        "bedrock_payload": "",
        "dt_synthesis": "",
        "pinky_tldr": "[ZERO_CONTEXT]: No matching records found.",
        "vibe": "TECHNICAL",
    }
    result = hub.step_trace_attribution(artifacts, user_feedback="Why did RAG find nothing?")
    assert result["defect_stage"] == "STAGE_2_RETRIEVAL_GAP"
    assert "returned 0 candidate chunks" in result["reason"].lower()


def test_step_trace_detects_stage1_triage_misclassification():
    """Check 5: User explicitly reports triage / vibe misclassification."""
    hub = CognitiveHub.__new__(CognitiveHub)
    artifacts = {
        "query": "Kernel panic crash trace on storage-02",
        "vibe": "CASUAL",
        "candidate_count": 0,
        "pinky_tldr": "Good morning Jason!",
    }
    result = hub.step_trace_attribution(artifacts, user_feedback="Wrong triage intent, this was a FORENSIC crash")
    assert result["defect_stage"] == "STAGE_1_TRIAGE_MISCLASSIFICATION"
    assert "misclassified" in result["reason"].lower()


def test_record_negative_exemplar_atomic_write():
    """record_negative_exemplar creates directory, appends entry, and updates timestamp atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "negative_exemplars.json")
        entry = record_negative_exemplar(
            query="test query",
            defect_stage="STAGE_4_HALLUCINATION",
            attribution_reason="Entailment audit tagged mismatch",
            response="hallucinated response",
            request_id="req-123",
            step_artifacts={"vibe": "TECHNICAL"},
            output_path=out_path,
        )
        assert os.path.exists(out_path)
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == "1.0"
        assert len(data["exemplars"]) == 1
        assert data["exemplars"][0]["request_id"] == "req-123"
        assert data["exemplars"][0]["defect_stage"] == "STAGE_4_HALLUCINATION"
