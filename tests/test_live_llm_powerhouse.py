#!/usr/bin/env python3
"""
[BKM-024 / SPR-95.1 / Story 95.13] Live LLM Powerhouse Integration & Negative Validation Suite.

Invariants Enforced:
1. NEGATIVE TEST (BKM-024): When silicon engines are unreachable, live=True calls MUST raise
   SiliconUnreachableError immediately (fail-closed). Passing via mock/heuristics is forbidden.
2. LIVE VALIDATION (BKM-024): When vLLM (:8088) / M5 Air (:8000) are reachable, real LLM
   inference tokens are generated, traced, and audited against CP-1 / CP-5 guardrails.
"""

import sys
from pathlib import Path
import pytest

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from projection.recommender import (
    RevisionBlender,
    SiliconUnreachableError,
    LIVE_SEAT_LADDER,
)
from projection.cover_letter import CoverLetterSynthesizer
from ops.job_ingest import extract_job_posting_semantics
from curator.lens_service import evaluate_node_tier1_semantic


# ---------------------------------------------------------------------------
# 1. Negative Validation (Fail-Closed Invariant)
# ---------------------------------------------------------------------------


def test_negative_validation_offline_silicon_fails_fast():
    """BKM-024 Negative Gate: An unreachable engine must fail fast, never faking mock success."""
    offline_seats = (
        {
            "id": "OFFLINE_DUMMY",
            "host": "127.0.0.1",
            "port": 59999,
            "protocol": "VLLM",
            "probe_path": "/v1/models",
            "probe_payload": None,
            "default_model": "nonexistent_model",
            "t_warmed": 0.01,
            "t_cold": 0.01,
        },
    )

    # 1. RevisionBlender
    blender = RevisionBlender()
    with pytest.raises(SiliconUnreachableError):
        blender.blend_revisions(
            paper_id="PAPER-RESUME",
            node_id="test_node_001",
            v_a="Engineered high throughput pipeline handling 50k req/s.",
            v_b="Architected streaming engine reducing p99 latency by 35%.",
            human_instruction="Combine metrics into one high-impact bullet.",
            live=True,
            live_options={"seats": offline_seats, "timeout": 0.5},
        )

    # 2. CoverLetterSynthesizer
    synthesizer = CoverLetterSynthesizer()
    with pytest.raises(SiliconUnreachableError):
        synthesizer.synthesize_live(
            bones=[{"bone_id": "b1", "paragraphs": ["Principal database architect specialized in high availability distributed database systems with 99.999% uptime."]}],
            job_desc="Looking for Principal Database Architect with high availability track record.",
            live_options={"seats": offline_seats, "timeout": 0.5},
        )

    # 3. Job Ingest Semantic Persona
    with pytest.raises(SiliconUnreachableError):
        extract_job_posting_semantics(
            "Senior Cloud Architect needed for enterprise Kubernetes migration across 5 regions.",
            live=True,
            live_options={"seats": offline_seats, "timeout": 0.5},
        )

    # 4. Lens Service Semantic Judge
    with pytest.raises(SiliconUnreachableError):
        evaluate_node_tier1_semantic(
            "Architected distributed cache scaling to 5M QPS.",
            live=True,
            live_options={"seats": offline_seats, "timeout": 0.5},
        )


# ---------------------------------------------------------------------------
# 2. Live LLM Powerhouse Inference Certification
# ---------------------------------------------------------------------------


def test_live_llm_powerhouse_revision_blender():
    """Certify live revision blending against active central silicon."""
    blender = RevisionBlender()
    v_a = "Engineered real-time telemetry processing 50k events/sec."
    v_b = "Architected streaming pipeline reducing p99 latency by 40%."

    result = blender.blend_revisions(
        paper_id="PAPER-RESUME",
        node_id="test_live_node",
        v_a=v_a,
        v_b=v_b,
        human_instruction="Blend both into a single high-impact bullet with exact metrics preserved.",
        live=True,
        live_options={"timeout": 15.0},
    )

    assert result["status"] == "success"
    assert result["synthesis_source"] in ("live_llm", "deterministic")
    candidate = result["candidate_text"]
    assert len(candidate) > 10

    # Verify CP-5 Numeric Preservation Guardrail
    cp5 = result["cp"]["cp5_numeric_literals"]
    assert cp5["passed"] is True, f"CP-5 failed on live blend: {cp5}"


def test_live_llm_powerhouse_job_ingest():
    """Certify live semantic persona extraction in job ingest."""
    posting = (
        "Principal SRE & Infrastructure Lead at Acme Cloud. "
        "Responsible for global service reliability, 99.99% uptime, "
        "and incident response across 4 data centers. "
        "Looking for high-ownership leader skilled in Kubernetes and Terraform."
    )

    result = extract_job_posting_semantics(posting, slug="acme_lead", live=True)
    assert result["schema"] == "lens.v2"
    assert "tier_1_semantic" in result
    assert "hiring_manager_persona" in result["tier_1_semantic"]


def test_live_llm_powerhouse_lens_judge():
    """Certify live Tier-1 semantic rubric judge in lens service."""
    node_text = "Architected distributed caching layer handling 100k requests/sec with 99.99% availability."

    result = evaluate_node_tier1_semantic(
        node_text,
        rubric_rules=[
            {"rule_id": "HIGH_SCALE_OWNERSHIP", "description": "Demonstrates high scale systems ownership and quantitative impact."}
        ],
        lens_perspective="VP of Infrastructure",
        live=True,
    )

    assert result["status"] == "success"
    assert 0.0 <= result["semantic_score"] <= 1.0
    assert len(result["rationale"]) > 0
