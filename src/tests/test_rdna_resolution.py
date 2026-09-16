"""
Test suite for Reverse DNA (RDNA) Question Matching and Bidirectional Linking.
Sprint: SPR-83.0 / Story 83.3
"""
import pytest
from logic.vector_pre_triage import probe_clara_dna_sync


def test_rdna_creative_code_question_resolution():
    """Verify that asking about code development or creative workflow matches RDNA-001 / PHL-032."""
    res = probe_clara_dna_sync("How do you brainstorm and develop code?")
    assert res is not None
    assert "rdna" in res["results_by_collection"]
    rdna_res = res["results_by_collection"]["rdna"]
    assert rdna_res["distance"] < 0.65
    assert rdna_res["metadata"]["target_dna_id"] == "PHL-032"
    assert "creative-process" in rdna_res["metadata"]["tags"]


def test_rdna_agentic_workflow_question_resolution():
    """Verify that asking about AI coding agents matches RDNA-002 / PHL-002."""
    res = probe_clara_dna_sync("How do you use AI agents in your software engineering?")
    assert res is not None
    assert "rdna" in res["results_by_collection"]
    rdna_res = res["results_by_collection"]["rdna"]
    assert rdna_res["distance"] < 0.65
    assert rdna_res["metadata"]["target_dna_id"] == "PHL-002"


def test_rdna_decoupling_question_resolution():
    """Verify that asking about architectural decoupling matches RDNA-005 / PHL-031."""
    res = probe_clara_dna_sync("Why is architectural decoupling important in complex software?")
    assert res is not None
    assert "rdna" in res["results_by_collection"]
    rdna_res = res["results_by_collection"]["rdna"]
    assert rdna_res["distance"] < 0.65
    assert rdna_res["metadata"]["target_dna_id"] == "PHL-031"
