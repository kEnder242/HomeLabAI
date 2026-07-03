import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

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


async def test_fuzzy_temporal_routing():
    """
    [Goal 3] Verification for Fuzzy Temporal Compass Routing.
    Tests neighborhood retrieval accuracy across year-end boundaries.
    """
    print("\n--- [GOAL 3] VERIFICATION: FUZZY TEMPORAL COMPASS ROUTING ---")

    with patch("nodes.archive_node.wisdom") as mock_wisdom, \
         patch("nodes.archive_node.stream") as mock_stream, \
         patch("nodes.archive_node.keyword_search") as mock_keyword:
        
        # Scenario: RRF returns 3 candidates with different timestamps
        mock_wisdom.query.return_value = {
            "documents": [
                ["MCTP driver setup (old)", "MCTP stress tests on Purley", "Resolved MCTP bus conflicts (new)"]
            ],
            "metadatas": [
                [
                    {"timestamp": "2017-06-20"},
                    {"timestamp": "2018-10-15"},
                    {"timestamp": "2019-01-05"}
                ]
            ]
        }
        mock_stream.query.return_value = {"documents": [[]], "metadatas": [[]]}
        mock_keyword.return_value = []
        
        # Query specifies "late 2018".
        # 2018-10-15 is 17 days away.
        # 2019-01-05 is 65 days away (spans year-end!).
        # 2017-06-20 is 500+ days away (should be penalized below top 2).
        ctx_res_raw = await get_context("MCTP cycle tests in late 2018", n_results=2)
        ctx_res = json.loads(ctx_res_raw)
        
        print(f"[STEP 1] Fuzzy routing context text:\n{ctx_res['text']}\n")
        
        # Top 2 results should contain the 2018-10-15 and 2019-01-05 items
        # and exclude the 2017 item
        assert "Purley" in ctx_res["text"]
        assert "bus conflicts" in ctx_res["text"]
        assert "driver setup" not in ctx_res["text"]

    print("✅ Goal 3 Verification: Fuzzy Temporal Compass Routing verified.")


async def test_relational_neighborhood_expansion():
    """
    [Goal 8] Verification for Relational Neighborhood Expansion.
    Tests that context extraction retrieves adjacent nodes from graph_relations.json.
    """
    print("\n--- [GOAL 8] VERIFICATION: RELATIONAL NEIGHBORHOOD EXPANSION ---")

    mock_relations = [
        {"source": "MCTP", "target": "PECI", "type": "RESOLVES"},
        {"source": "Montana", "target": "MCTP", "type": "UTILIZES"}
    ]

    with patch("nodes.archive_node.wisdom") as mock_wisdom, \
         patch("nodes.archive_node.stream") as mock_stream, \
         patch("nodes.archive_node.keyword_search") as mock_keyword, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(mock_relations))):
        
        mock_wisdom.query.return_value = {
            "documents": [
                ["MCTP driver setup on Montana board"]
            ],
            "metadatas": [
                [
                    {"timestamp": "2018-10-15"}
                ]
            ]
        }
        mock_stream.query.return_value = {"documents": [[]], "metadatas": [[]]}
        mock_keyword.return_value = []
        
        ctx_res_raw = await get_context("MCTP setup", n_results=1)
        ctx_res = json.loads(ctx_res_raw)
        
        print(f"[STEP 1] Relational neighborhood context:\n{ctx_res['text']}\n")
        
        # Verify that relational expansion contains the mock relations
        assert "[RELATIONAL_NEIGHBOR_EXPANSION]" in ctx_res["text"]
        assert "MCTP --[RESOLVES]--> PECI" in ctx_res["text"]
        assert "Montana --[UTILIZES]--> MCTP" in ctx_res["text"]

    print("✅ Goal 8 Verification: Relational Neighborhood Expansion verified.")


async def main():
    await test_archive_rrf_logic()
    await test_fuzzy_temporal_routing()
    await test_relational_neighborhood_expansion()


if __name__ == "__main__":
    asyncio.run(main())
