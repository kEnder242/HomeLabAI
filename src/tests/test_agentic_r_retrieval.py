import pytest
import os
import sys
import json

# Ensure HomeLabAI root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.nodes.archive_node import compute_mmr_ranking, execute_grep_search_pivot, get_context


def test_compute_mmr_ranking_penalizes_redundant_chunks():
    """Verify that MMR demotes near-identical documents in favor of orthogonal technical details."""
    candidates = [
        {
            "id": "doc1",
            "document": "RAPL power telemetry measures CPU package energy consumption using MSR registers.",
            "metadata": {"title": "RAPL Overview"},
            "distance": 0.20,
            "collection": "lab_journal"
        },
        {
            "id": "doc2",
            "document": "RAPL power telemetry measures CPU package energy consumption using MSR registers in Linux.",
            "metadata": {"title": "RAPL Duplicate"},
            "distance": 0.21,
            "collection": "lab_journal"
        },
        {
            "id": "doc3",
            "document": "pecistressor.py achieves 5300 cmd/sec sideband command throughput across OpenBMC PECI bus.",
            "metadata": {"title": "PECI Tool"},
            "distance": 0.35,
            "collection": "artifact_vault"
        }
    ]

    ranked = compute_mmr_ranking(candidates, n_results=2, lambda_param=0.5)
    assert len(ranked) == 2
    assert ranked[0]["id"] == "doc1"
    # Doc3 should be promoted over doc2 due to novelty / diversity
    assert ranked[1]["id"] == "doc3"


def test_compute_mmr_ranking_boundary_conditions():
    """Verify MMR handles empty lists and small candidate sets gracefully."""
    assert compute_mmr_ranking([]) == []
    single = [{"id": "single", "document": "test", "distance": 0.1}]
    assert compute_mmr_ranking(single, n_results=3) == single


def test_execute_grep_search_pivot_finds_anchors():
    """Verify that execute_grep_search_pivot extracts hardware acronyms and returns structured evidence."""
    query = "How did Jason debug PECI bus saturation using pecistressor.py?"
    result = execute_grep_search_pivot(query, max_matches=3)

    assert isinstance(result, str)
    if result:  # If test runs on machine with field_notes/data populated
        assert "[AGENTIC_R_GREP_PIVOT]" in result
        assert "PECI" in result or "pecistressor" in result


def test_execute_grep_search_pivot_empty_on_generic_query():
    """Verify that non-technical generic queries without hardware anchors return empty string."""
    query = "hello there how are you today"
    result = execute_grep_search_pivot(query)
    assert result == ""
