"""Tests for the multi-collection reranker in archive_node.get_context()."""
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from nodes.archive_node import get_context


MOCK_COLLECTION_RESPONSES = {
    "behavioral_dna": {
        "ids": [["bkm_001", "bkm_002"]],
        "distances": [[0.32, 0.48]],
        "metadatas": [[{"bkm_id": "BKM-012"}, {"bkm_id": "BKM-013"}]],
        "documents": [["Behavioral DNA entry 1", "Behavioral DNA entry 2"]]
    },
    "feature_dna": {
        "ids": [["feat_001", "feat_002"]],
        "distances": [[0.28, 0.55]],
        "metadatas": [[{"feat_id": "FEAT-304"}, {"feat_id": "FEAT-305"}]],
        "documents": [["Feature DNA entry 1", "Feature DNA entry 2"]]
    },
    "career_ledger": {
        "ids": [["career_001", "career_002"]],
        "distances": [[0.35, 0.42]],
        "metadatas": [[{"era": "2023", "skill": "Python"}, {"era": "2024", "skill": "Rust"}]],
        "documents": [["Career entry 1", "Career entry 2"]]
    },
    "artifact_vault": {
        "ids": [["art_001", "art_002"]],
        "distances": [[0.40, 0.60]],
        "metadatas": [[{"title": "Design Doc", "gdrive_link": "https://drive.google.com/1"},
                       {"title": "Spec", "gdrive_link": ""}]],
        "documents": [["Artifact entry 1", "Artifact entry 2"]]
    },
    "lab_journal": {
        "ids": [["lab_001", "lab_002"]],
        "distances": [[0.30, 0.50]],
        "metadatas": [[{"note_id": "NOTE-001"}, {"note_id": "NOTE-002"}]],
        "documents": [["Lab journal entry 1", "Lab journal entry 2"]]
    }
}


def _make_post_acm(url, json, **kwargs):
    for coll_name, resp_data in MOCK_COLLECTION_RESPONSES.items():
        if coll_name in url:
            resp = AsyncMock()
            resp.status = 200
            resp.json = AsyncMock(return_value=resp_data)
            break
    else:
        resp = AsyncMock()
        resp.status = 404
        resp.json = AsyncMock(return_value={})
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@patch("aiohttp.ClientSession")
def test_multi_collection_reranker(MockSession):
    """get_context queries 5 collections and applies reranker with distance cutoff."""
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=session_cm)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    MockSession.return_value = session_cm

    session_cm.post = MagicMock(side_effect=_make_post_acm)

    result = asyncio.run(get_context("test query", n_results=10))

    assert "[MULTI_COLLECTION_RERANKER]" in result
    assert "[ARTIFACT:" in result
    assert "[CAREER:" in result
    assert "[BEHAVIORAL_DNA:" in result
    assert "[FEATURE_DNA:" in result
    assert "[LAB_JOURNAL:" in result

    assert "FEATURE_DNA: FEAT-304" in result
    assert "LAB_JOURNAL: NOTE-001" in result
    assert "BEHAVIORAL_DNA: BKM-012" in result
    assert "CAREER: 2023" in result
    assert "ARTIFACT: Design Doc" in result
    assert "gdrive_link" not in result, "gdrive_link metadata field should not leak raw"
    assert "https://drive.google.com/1" in result, "gdrive link should appear in badge"


if __name__ == "__main__":
    test_multi_collection_reranker()
    print("[PASS] ALL CHECKS PASSED")
