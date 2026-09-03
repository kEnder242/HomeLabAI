import pytest

def test_no_hardcoded_greeting_lists():
    """[BKM-015 Enforcement]: Ensure cognitive_hub.py contains zero static greeting string lists in executable code."""
    with open("src/logic/cognitive_hub.py", "r") as f:
        lines = f.readlines()
    
    # Assert raw_lower greeting list matching is strictly forbidden in code
    for line in lines:
        if line.strip().startswith("#"):
            continue
        assert "raw_lower in [" not in line, "BKM-015 Violation: Hardcoded greeting list found in cognitive_hub.py"
        assert 'if raw_lower in' not in line, "BKM-015 Violation: Hardcoded greeting list found in cognitive_hub.py"

def test_triage_taxonomy_contains_unknown_domain():
    """Verify unknown domain is available as an explicit escape hatch."""
    with open("src/logic/cognitive_hub.py", "r") as f:
        content = f.read()
    
    assert '"unknown"' in content, "Triage schema must contain 'unknown' domain enum"
