"""Integration test for the RAG matrix multi-collection query."""
import asyncio
import json
import time

from nodes.archive_node import get_context


def test_integration_rag_matrix():
    """Queries real ChromaDB via get_context and checks response payload."""
    query = "PCIe RAS telemetry validation"

    start = time.perf_counter()
    result = asyncio.run(get_context(query, n_results=3))
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Parse the JSON response
    payload = json.loads(result)
    text = payload.get("text", "")

    # Assert context is non-empty
    assert text, f"Context is empty for query: {query}"

    # Assert sources list is populated
    sources = payload.get("sources", [])
    assert len(sources) > 0, "No sources returned in RAG payload"

    # Assert badging / acquisition anchors appear in text
    assert any(badge in text for badge in ["[ACQUISITION", "[ARTIFACT:", "[CAREER:", "[BEHAVIORAL_DNA:", "[FEATURE_DNA:", "[LAB_JOURNAL:"]), "No domain badges or acquisition anchors found in payload"

    # Assert execution time is reasonable (<5000ms)
    assert elapsed_ms < 5000, f"Execution time {elapsed_ms:.1f}ms exceeded 5000ms"

    print(f"[PASS] INTEGRATION RAG MATRIX: {elapsed_ms:.1f}ms, {len(text)} chars, {len(payload.get('sources', []))} sources")


if __name__ == "__main__":
    test_integration_rag_matrix()
    print("[PASS] ALL CHECKS PASSED")
