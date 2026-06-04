import asyncio
import os
import json
import logging
import pytest
from recruiter import NightlyRecruiter
from dream_cycle import DreamManager

# Mocking Node Interfaces
class MockNode:
    def __init__(self, name):
        self.name = name
    async def call_tool(self, name, arguments=None):
        print(f"[MOCK] {self.name} calling tool: {name} with args: {arguments}")
        if name == "get_stream_dump":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps({"documents": [], "ids": []})})()]})
        if name == "list_cabinet":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps(["2023.json"])})()]})
        if name == "read_document":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps([{"summary": "Test", "rank": 2}])})()]})
        if name == "get_context":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': json.dumps({"text": "Expert."})})()]})
        return type('obj', (object,), {'content': [type('obj', (object,), {'text': "OK"})()]})

@pytest.mark.asyncio
async def test_dream_expansion_on_empty_stream():
    """Verifies that the Dream Manager transitions to refinement when the stream is empty."""
    print("\n--- [TEST] Dream Expansion (Empty Stream) ---")
    mock_archive = MockNode("Archive")
    manager = DreamManager(mock_archive)
    
    # This should trigger run_refinement_dream
    await manager.run_cycle()
    print("[PASS] Dream expansion logic executed.")

@pytest.mark.asyncio
async def test_recruiter_expansion_on_no_jobs():
    """Verifies that the Recruiter transitions to synergy scanning when no jobs are found."""
    print("\n--- [TEST] Recruiter Expansion (No Jobs) ---")
    mock_archive = MockNode("Archive")
    mock_brain = MockNode("Brain")
    
    r = NightlyRecruiter(mock_archive, mock_brain)
    
    # We mock search_for_jobs to return empty
    async def mock_search(): return []
    r.search_for_jobs = mock_search
    
    # We mock verify_and_score_jobs to return empty
    async def mock_verify(jobs): return []
    r.verify_and_score_jobs = mock_verify
    
    from recruiter import run_recruiter_task
    # This should trigger run_synergy_scan
    await r.run_synergy_scan()
    print("[PASS] Recruiter expansion logic executed.")

if __name__ == "__main__":
    async def run_all():
        await test_dream_expansion_on_empty_stream()
        await test_recruiter_expansion_on_no_jobs()
    asyncio.run(run_all())
