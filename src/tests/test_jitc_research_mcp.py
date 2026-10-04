import json
import os
import sys

# Add the source directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../AcmeLab/src")))

import clara_dna_mcp_server

def test_stage_research_persists_plan():
    res = clara_dna_mcp_server.stage_research(
        file_path="src/logic/processor.py",
        plan_content="Refactor vector query pipeline",
        patch_blueprint="<<<SEARCH\nold_code()\n===\nnew_code()\n>>>",
        ast_anchors=["class VectorProcessor", "def query()"],
        diff_directives=["Replace sync urllib with async REST client"]
    )
    assert res["status"] == "staged"
    assert res["file_path"] == "src/logic/processor.py"

    # Verify research tool recalls this staged plan as fresh empirical findings
    result = clara_dna_mcp_server.research("src/logic/processor.py")
    assert "Conductor Blueprint: Applied Scalpel Match for src/logic/processor.py" in result
    assert "class VectorProcessor" in result
    assert "new_code()" in result
    assert "Refactor vector query pipeline" in result


def test_research_tool():
    # Test staging and recalling
    clara_dna_mcp_server.stage_research(
        file_path="dummy_file.py",
        plan_content="test notes",
        patch_blueprint="patch_blueprint_content",
        ast_anchors=["anchor1"]
    )
        
    result = clara_dna_mcp_server.research("dummy_file.py")
    assert "Conductor Blueprint: Applied Scalpel Match for dummy_file.py" in result
    assert "anchor1" in result
    assert "patch_blueprint_content" in result
    
    # Fallback test
    fallback_result = clara_dna_mcp_server.research("unseen_file.py")
    assert "Fallback Analysis for unseen_file.py:" in fallback_result

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
