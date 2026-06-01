import asyncio
import json
import os
import logging
from unittest.mock import AsyncMock, MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set environment variables for paths
os.environ["WORKSPACE_DIR"] = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
os.environ["LAB_DIR"] = os.path.expanduser("~/Dev_Lab/HomeLabAI")

from nodes.archive_node import (
    scribble_to_clipboard, 
    read_clipboard, 
    clear_clipboard, 
    get_context, 
    SESSION_CLIPBOARD,
    DATA_DIR
)

async def test_archive_clipboard_logic():
    """
    [Task 3.1] Verification for Clipboard and Neighborhood Expansion.
    """
    print("\n--- [TASK 3.1] VERIFICATION: ARCHIVE CLIPBOARD ---")
    
    # 1. Test Scribble & Read
    await clear_clipboard()
    res = await scribble_to_clipboard("Test context segment")
    print(f"[STEP 1] Scribble result: {res}")
    
    cb = await read_clipboard()
    print(f"[STEP 1] Clipboard content: {cb}")
    assert "Test context segment" in cb
    
    # 2. Test get_context with Clipboard
    # Mocking ChromaDB collections
    with patch("nodes.archive_node.wisdom") as mock_wisdom, \
         patch("nodes.archive_node.stream") as mock_stream, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", MagicMock()):
        
        # Scenario: No vector matches, but clipboard has content
        mock_wisdom.query.return_value = {"documents": [[]], "metadatas": [[]]}
        mock_stream.query.return_value = {"documents": [[]], "metadatas": [[]]}
        
        ctx_res_raw = await get_context("Tell me anything")
        ctx_res = json.loads(ctx_res_raw)
        
        print(f"[STEP 2] get_context with empty vector results but full clipboard: {ctx_res['text'][:50]}...")
        assert "SESSION_CLIPBOARD" in ctx_res["text"]
        assert "Test context segment" in ctx_res["text"]

    # 3. Test Neighborhood Expansion
    print("\n--- [STEP 3] NEIGHBORHOOD EXPANSION ---")
    await clear_clipboard()
    
    test_json_data = [
        {"id": "GEM-001", "summary": "Prev entry"},
        {"id": "GEM-002", "summary": "Target entry for expansion"},
        {"id": "GEM-003", "summary": "Next entry"}
    ]
    
    with patch("nodes.archive_node.wisdom") as mock_wisdom, \
         patch("nodes.archive_node.stream") as mock_stream, \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=json.dumps(test_json_data)))))))):
        
        # Scenario: Found a vector match that points to a JSON file
        mock_wisdom.query.return_value = {
            "documents": [["Target entry"]],
            "metadatas": [[{"source": "2024_02.json"}]]
        }
        
        # We need a custom mock for open to return different content based on filename
        def side_effect_open(path, mode='r'):
            m = MagicMock()
            m.__enter__.return_value = m
            if "2024_02.json" in path:
                m.read.return_value = json.dumps(test_json_data)
            else:
                m.read.return_value = "{}"
            return m

        with patch("builtins.open", side_effect=side_effect_open):
            ctx_res_raw = await get_context("RAPL kernel fix")
            ctx_res = json.loads(ctx_res_raw)
            
            print(f"[STEP 3] get_context triggered expansion.")
            
            # Check if neighbors were added to clipboard
            cb_after = await read_clipboard()
            print(f"[STEP 3] Clipboard after expansion:\n{cb_after}")
            
            assert "Prev entry" in cb_after
            assert "Next entry" in cb_after
            assert "NEIGHBORHOOD_EXPANSION" in cb_after

    print("\n✅ Task 3.1 Verification: Clipboard and Expansion verified.")

if __name__ == "__main__":
    asyncio.run(test_archive_clipboard_logic())
