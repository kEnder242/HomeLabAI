#!/usr/bin/env python3
"""
[FEAT-485] Live Prompt Turn & Epistemological Reasoning Evaluator

A lightweight CLI and pytest harness allowing instant iteration on prompt engineering
and behavioral guidance against live Ollama / resident models without restarting vLLM.

Usage:
  # Run as a pytest unit test:
  pytest -v src/tests/test_live_prompt_turn.py

  # Run as a dynamic live evaluation CLI:
  python3 src/tests/test_live_prompt_turn.py --query "was Kayak really in 2008?" --dry-run
"""

import argparse
import asyncio
import json
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure src in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Mock dependencies if running in system Python
for mod in ['chromadb', 'aiohttp', 'fastmcp', 'fastembed']:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import src.nodes.archive_node


async def evaluate_live_turn(query: str, target_year: str = None, dry_run: bool = False):
    """Evaluates a live query through Archive RAG and epistemological synthesis."""
    from src.nodes.archive_node import get_context

    # 1. Fetch RAG Context & Scarcity Diagnostics
    rag_json = await get_context(query=query, domain="lab_history")
    rag_data = json.loads(rag_json) if isinstance(rag_json, str) else rag_json
    rag_context = rag_data.get("context", "")
    rag_found = rag_data.get("found", False)

    # 2. Build Behavioral Guidance Prompt
    behavioral_guidance = (
        "[MODE]: SYNTHESIS (Speak conversationally, using the provided context as background knowledge.)"
    )
    if "[ARCHIVAL_EVIDENCE]" in rag_context:
        behavioral_guidance += (
            " EPISTEMOLOGICAL_PROTOCOL: The provided [ARCHIVAL_EVIDENCE] contains temporal scarcity diagnostics from the 18-year archive. "
            "Synthesize these facts: if an entity was active in other years but has 0 records in the queried year, deduce and state definitively "
            "that the entity was NOT present/active during that target year. State the true active years from the evidence and conclude without passive conversational hedging or asking for clarification."
        )
    elif not rag_found:
        behavioral_guidance += (
            " ZERO_CONTEXT_PROTOCOL: No relevant historical notes were found for this query. "
            "In this 18-year archive, the absence of records for a requested entity or year indicates it was NOT present/active during that timeframe. "
            "State definitively that no records exist in the archive rather than passively asking for clarification. "
            "Do NOT invent or hallucinate legacy records, dates, or accomplishments."
        )

    system_prompt = (
        f"You are Pinky, an AI platform validation engineer in the Acme Lab.\n"
        f"Behavioral Guidance: {behavioral_guidance}\n\n"
        f"Context:\n{rag_context}\n"
    )

    result = {
        "query": query,
        "rag_found": rag_found,
        "has_scarcity_envelope": "[ARCHIVAL_EVIDENCE]" in rag_context,
        "rag_context_preview": rag_context[:300] + ("..." if len(rag_context) > 300 else ""),
        "system_prompt": system_prompt,
        "response": None,
        "deduction_passed": None
    }

    if dry_run:
        return result

    # 3. Stream from remote Ollama (Deep Thought / Kender) or fallback to local
    import urllib.request
    ollama_url = os.environ.get("OLLAMA_HOST", "http://192.168.1.26:11434")
    try:
        req_data = json.dumps({
            "model": "llama3.1:8b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "stream": False,
            "options": {"temperature": 0.3}
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                response_text = data.get("message", {}).get("content", "")
                result["response"] = response_text
                
                # Evaluate negative deductive reasoning
                hedging_triggers = ["can you clarify", "please provide more context", "i don't have enough information"]
                is_hedging = any(h in response_text.lower() for h in hedging_triggers)
                result["deduction_passed"] = not is_hedging
            else:
                result["response"] = f"[HTTP {resp.status}] Ollama unreachable"
    except Exception as e:
        result["response"] = f"[Ollama Error]: {e}"

    return result


def test_epistemic_scarcity_prompt_dry_run():
    """Unit test asserting prompt assembly without external LLM call."""
    mock_fused = [
        (
            "doc_2014_1",
            {
                "date": "2014-06-15",
                "timestamp": "2014_06",
                "source": "2014_06.json",
                "text_anchor": "Kayak PCIe telemetry validation framework deployment",
                "summary": "Kayak PCIe telemetry validation framework",
                "_rrf_score": 0.95
            }
        )
    ]
    with patch("src.nodes.archive_node.embed_texts", return_value=[[0.1] * 384]), \
         patch("src.nodes.archive_node.wisdom.query", return_value={"documents": [[]], "metadatas": [[]]}), \
         patch("src.nodes.archive_node.stream.query", return_value={"documents": [[]], "metadatas": [[]]}), \
         patch("src.nodes.archive_node.keyword_search", return_value=[]), \
         patch("src.nodes.archive_node.rrf_fuse", return_value=mock_fused), \
         patch("src.nodes.archive_node.get_observational_memo", return_value=""), \
         patch("os.path.exists", side_effect=lambda p: False if "2008.json" in p or "2007.json" in p else True):

        res = asyncio.run(evaluate_live_turn(query="was Kayak really in 2008?", dry_run=True))
        assert res["has_scarcity_envelope"] is True
        assert "EPISTEMOLOGICAL_PROTOCOL" in res["system_prompt"]
        assert "temporal scarcity diagnostics" in res["system_prompt"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Prompt Turn Evaluator")
    parser.add_argument("--query", type=str, default="was Kayak really in 2008?", help="Query to test")
    parser.add_argument("--dry-run", action="store_true", help="Only assemble and display prompt without calling LLM")
    args = parser.parse_args()

    print(f"\n--- Testing Live Turn: '{args.query}' (Dry Run: {args.dry_run}) ---")
    out = asyncio.run(evaluate_live_turn(query=args.query, dry_run=args.dry_run))
    print(f"RAG Found: {out['rag_found']}")
    print(f"Scarcity Envelope: {out['has_scarcity_envelope']}")
    print(f"\n[Context Preview]:\n{out['rag_context_preview']}")
    print(f"\n[System Prompt Preview]:\n{out['system_prompt']}")
    if out["response"]:
        print(f"\n[Model Response]:\n{out['response']}")
        print(f"\nDeduction Assessment (No Hedging): {'✅ PASS' if out['deduction_passed'] else '❌ FAIL'}")
