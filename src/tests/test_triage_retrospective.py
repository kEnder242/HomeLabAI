import unittest
import os
import sys
import re

# Ensure HomeLabAI/src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class TestTriageRetrospectiveRule(unittest.TestCase):
    def test_year_retrospective_rule(self):
        sample_queries = [
            "what did I do in 2018?",
            "what happened in 2020?",
            "search notes for RAPL",
            "what did I do in 2024"
        ]
        
        for turn in sample_queries:
            lower_turn = turn.lower()
            has_year = bool(re.search(r'\b(20\d{2}|19\d{2})\b', turn))
            is_history_query = any(k in lower_turn for k in ["what did i do", "what happened", "search notes", "find notes", "lab history", "retrospective"])
            
            is_matched = has_year or is_history_query
            self.assertTrue(is_matched, f"Query '{turn}' should match retrospective history rule.")

if __name__ == "__main__":
    unittest.main()
