"""
Unit Test Suite for [FEAT-630 / Story 95.14]:
RDNA-Assisted HyDE Semantic Expansion Bridge.
"""

import pytest
from src.nodes.archive_node import (
    resolve_rdna_hyde_exemplar,
    select_vector_query,
    parse_multi_voice_hyde,
)


class MockChromaCollection:
    def __init__(self, items):
        self.items = items

    def query(self, query_texts, n_results=1):
        q = query_texts[0].lower()
        for item in self.items:
            if any(w in q for w in item["keywords"]):
                return {
                    "ids": [[item["id"]]],
                    "distances": [[item["dist"]]],
                    "metadatas": [[item["metadata"]]],
                }
        return {"ids": [[]], "distances": [[]], "metadatas": [[]]}


class MockChromaClient:
    def __init__(self, collection):
        self._col = collection

    def get_collection(self, name):
        if name == "rdna":
            return self._col
        raise ValueError(f"Unknown collection {name}")


@pytest.fixture
def mock_rdna_client():
    col = MockChromaCollection(
        [
            {
                "id": "RDNA-002",
                "keywords": ["philosophy", "agentic", "workflows", "delegation"],
                "dist": 0.25,
                "metadata": {
                    "id": "RDNA-002",
                    "title": "Agentic AI Workflow Philosophy",
                    "question": "What is your philosophy on agentic AI workflows and LLMs in engineering?",
                    "target_dna": {
                        "collection": "philosophy_dna",
                        "id": "PHL-002",
                        "title": "The Hippocampus & Prefrontal Cortex Architecture",
                    },
                },
            },
            {
                "id": "RDNA-003",
                "keywords": ["stability", "drift", "autonomous"],
                "dist": 0.55,  # Weak distance, exceeds threshold
                "metadata": {
                    "id": "RDNA-003",
                    "title": "Autonomous Multi-Agent Stability",
                    "target_dna": {
                        "id": "PHL-003",
                        "title": "The Single-Tenant Invariant",
                    },
                },
            },
        ]
    )
    return MockChromaClient(col)


def test_rdna_hyde_high_confidence_match(mock_rdna_client):
    """Verify high-confidence RDNA hit returns expanded query and metadata."""
    query = "Tell me about your agentic workflow philosophy"
    expansion, meta = resolve_rdna_hyde_exemplar(
        query, client=mock_rdna_client, distance_floor=0.45
    )
    assert meta.get("rdna_id") == "RDNA-002"
    assert "Hippocampus & Prefrontal Cortex" in expansion
    assert meta.get("confidence") == pytest.approx(0.75)


def test_rdna_hyde_low_confidence_fallback(mock_rdna_client):
    """Verify weak RDNA hit (> floor) falls back cleanly without expansion."""
    query = "How do we prevent drift in autonomous agents?"
    expansion, meta = resolve_rdna_hyde_exemplar(
        query, client=mock_rdna_client, distance_floor=0.45
    )
    assert meta == {}
    assert expansion == query


def test_select_vector_query_prefers_explicit_hyde(mock_rdna_client):
    """Verify explicit substantial hyde_vector_text takes precedence over RDNA."""
    raw = "What is the memory architecture?"
    explicit_hyde = "[VALIDATION]: ras | [STRATEGY]: goal | [SRE]: scar"
    selected = select_vector_query(raw, explicit_hyde)
    assert selected == "ras goal scar"
