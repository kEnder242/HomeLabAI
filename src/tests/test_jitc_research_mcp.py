import json
import os
import sys

# Add the source directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../AcmeLab/src")))

import clara_dna_mcp_server

def test_research_tool():
    # Write dummy notes
    notes_path = "/tmp/clara_conductor_notes.json"
    with open(notes_path, "w") as f:
        json.dump({"dummy_file.py": {"notes": "test notes", "ast_anchors": ["anchor1"], "diff_directives": []}}, f)
        
    result = clara_dna_mcp_server.research("dummy_file.py")
    assert "Structured Findings for dummy_file.py:" in result
    assert "test notes" in result
    
    # Fallback test
    fallback_result = clara_dna_mcp_server.research("other_file.py")
    assert "Fallback Analysis for other_file.py:" in fallback_result

def test_failure_whisperer_tool():
    test_output = "Some random text\nE   AssertionError: expected True but got False\nMore text"
    result = clara_dna_mcp_server.failure_whisperer(test_output)
    assert "AssertionError: expected True but got False" in result
    assert "Diagnosis:" in result

def test_handoff_checkpoint_tool():
    ledger_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/delegation_ledger.jsonl")
    if os.path.exists(ledger_path):
        os.remove(ledger_path)
    
    result = clara_dna_mcp_server.handoff_checkpoint("SUCCESS", "Test summary", ["file1.py"])
    assert result["status"] == "success"
    assert result["record"]["status"] == "SUCCESS"
    assert result["record"]["summary"] == "Test summary"
    
    with open(ledger_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["status"] == "SUCCESS"

def test_locate_path_tool():
    result = clara_dna_mcp_server.locate_path("pattern")
    assert result["pattern"] == "pattern"
    assert "results" in result
    
    # Test alias
    assert clara_dna_mcp_server.locate_grounding == clara_dna_mcp_server.locate_path
