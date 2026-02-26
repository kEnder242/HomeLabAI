import asyncio
import json
import os
import sys
import logging

# Setup Path
LAB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(LAB_ROOT, "src"))

from nodes.archive_node import get_context

async def test_rag_logic():
    print("--- [TEST] RAG Multi-Stage Discovery Logic ---")
    
    scenarios = [
        {"name": "Valid Year (2019)", "query": "Validation events from 2019", "expect_sources": True},
        {"name": "Missing Year (2010)", "query": "What happened in 2010?", "expect_sources": False},
        {"name": "No Year Filter", "query": "General architecture notes", "expect_sources": True}
    ]
    
    for s in scenarios:
        print(f"\nScenario: {s['name']}")
        res_json = await get_context(s['query'])
        try:
            res = json.loads(res_json)
            sources = res.get("sources", [])
            text = res.get("text", "")
            
            print(f"  Sources Found: {len(sources)}")
            if s['expect_sources'] and not sources:
                print(f"  WARNING: Expected sources for query but got none.")
            elif not s['expect_sources'] and sources:
                print(f"  FAILED: Unexpected sources for query: {sources}")
            else:
                print(f"  PASSED: Source expectation met.")
                
            if len(text) > 50:
                print(f"  Text Preview: {text[:60]}...")
            else:
                print(f"  Text: {text}")
                
        except Exception as e:
            print(f"  FAILED: Invalid JSON returned: {e}")
            print(f"  Raw: {res_json}")

if __name__ == "__main__":
    asyncio.run(test_rag_logic())
