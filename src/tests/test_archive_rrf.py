import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from nodes.archive_node import (
    rrf_fuse,
    keyword_search,
    get_context,
    DATA_DIR
)

async def test_archive_rrf_logic():
    """
    [Task 3.2] Verification for Hybrid Retrieval (RRF).
    """
    print("\n--- [TASK 3.2] VERIFICATION: HYBRID RETRIEVAL (RRF) ---")
    
    # 1. Test Keyword Search
    test_json = [
        {"id": "GEM-999", "summary": "Silicon validation of PECISTRESSOR tool."},
        {"id": "GEM-888", "summary": "Other random note."}
    ]
    
    with patch("glob.glob", return_value=["mock_data.json"]), \
         patch("builtins.open", side_effect=[MagicMock(__enter__=lambda s: MagicMock(read=lambda: json.dumps(test_json)))]):
        
        results = keyword_search("PECISTRESSOR")
        print(f"[STEP 1] Keyword search for PECISTRESSOR: {len(results)} matches.")
        assert len(results) > 0
        assert "PECISTRESSOR" in results[0][1]["text"]

    # 2. Test RRF Fusion
    vector_list = [("doc1", {"v": 1}), ("doc2", {"v": 2})]
    keyword_list = [("doc3", {"k": 3}), ("doc1", {"k": 1})]
    
    fused = rrf_fuse([vector_list, keyword_list])
    print(f"[STEP 2] RRF Fused results: {[r[0] for r in fused]}")
    
    # doc1 should be top because it appeared in both lists
    assert fused[0][0] == "doc1"
    assert len(fused) == 3

    # 3. Test get_context with RRF
    with patch("nodes.archive_node.wisdom") as mock_wisdom, \
         patch("nodes.archive_node.stream") as mock_stream, \
         patch("nodes.archive_node.keyword_search") as mock_keyword:
        
        # Scenario: Vector finds one thing, Keyword finds another (acronym)
        mock_wisdom.query.return_value = {
            "documents": [["Telemetry result"]],
            "metadatas": [[{"source": "vector.json"}]]
        }
        mock_stream.query.return_value = {"documents": [[]], "metadatas": [[]]}
        
        mock_keyword.return_value = [
            ("PECISTRESSOR", {"source": "acronym.json", "text_anchor": "PECISTRESSOR tool details"})
        ]
        
        ctx_res_raw = await get_context("Tell me about PECISTRESSOR")
        ctx_res = json.loads(ctx_res_raw)
        
        print(f"[STEP 3] get_context hybrid output: {ctx_res['text'][:100]}...")
        
        # Result should contain both vector and keyword anchor
        assert "PECISTRESSOR" in ctx_res["text"]
        assert "Telemetry result" in ctx_res["text"]

    print("\n✅ Task 3.2 Verification: Hybrid Retrieval (RRF) verified.")

if __name__ == "__main__":
    asyncio.run(test_archive_rrf_logic())
