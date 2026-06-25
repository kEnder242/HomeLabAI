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
        {"name": "Missing Year (1999)", "query": "What happened in 1999?", "expect_sources": False},
        {"name": "No Year Filter", "query": "General architecture notes", "expect_sources": True},
        {"name": "Domain Filter exp_tlm (Explicit)", "query": "Find monitoring metrics", "expect_sources": True, "domain": "exp_tlm"},
        {"name": "Domain Filter exp_bkm (Explicit)", "query": "Find validation procedures", "expect_sources": True, "domain": "exp_bkm"},
        {"name": "Domain Fallback from status.json (exp_tlm)", "query": "Find monitor stats", "expect_sources": True, "fallback_domain": "exp_tlm"}
    ]
    
    for s in scenarios:
        print(f"\nScenario: {s['name']}")
        
        status_path = os.path.join(LAB_ROOT, "Portfolio_Dev/field_notes/data/status.json")
        orig_data = None
        if "fallback_domain" in s:
            if os.path.exists(status_path):
                with open(status_path, "r") as f:
                    orig_data = json.load(f)
            new_data = {**(orig_data or {}), "active_domain": s["fallback_domain"]}
            with open(status_path, "w") as f:
                json.dump(new_data, f, indent=2)
                
        try:
            domain_param = s.get("domain")
            res_json = await get_context(s['query'], domain=domain_param)
            res = json.loads(res_json)
            sources = res.get("sources", [])
            text = res.get("text", "")
            
            if domain_param or s.get("fallback_domain"):
                d = domain_param or s.get("fallback_domain")
                print(f"  Filtering with Domain: {d}")
                
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
        finally:
            if "fallback_domain" in s and orig_data is not None:
                with open(status_path, "w") as f:
                    json.dump(orig_data, f, indent=2)

if __name__ == "__main__":
    asyncio.run(test_rag_logic())
