#!/usr/bin/env python3
"""
probe_phase3_rag_gauntlet.py — Phase 3 Empirical Gauntlet & Silicon Replay
[Phase 3: #3.4 / BKM-024 / BKM-088] Multi-Stage Verification Suite.

Validates:
1. Probe 3.4.1: Scope resolution & inclusive fallback logic (unit assertions).
2. Probe 3.4.2: Archive node live Chroma query against career_ledger for RAS/Mailbox evidence.
3. Probe 3.4.3: Turn isolation & anti-bleed state hygiene.
4. Probe 3.4.4: Full live silicon replay of Jason's 07:45 prompt against port 8765,
   verifying Brain/Pinky grounding, zero silicon telemetry leakage, and Bonsai Critic >= 0.85.
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, Tuple

try:
    import aiohttp
except ImportError:
    aiohttp = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("probe_phase3")

FOYER_URL = "http://127.0.0.1:8765"
WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..")
)
DATA_DIR = os.path.join(WORKSPACE_DIR, "Portfolio_Dev/field_notes/data")
STAGE_LEDGER_PATH = os.path.join(DATA_DIR, "foyer_stage_ledger.jsonl")
JUDGE_BACKPRESSURE_PATH = os.path.join(DATA_DIR, "judge_backpressure.jsonl")


def probe_3_4_1_scope_resolution() -> dict[str, Any]:
    """Probe 3.4.1: Scope resolution & inclusive fallback unit assertion."""
    logger.info("🧪 Running Probe 3.4.1: Scope Resolution & Inclusive Fallback...")
    from logic.traversal_dispatcher import resolve_collection_scope

    # Assertion 1: Exact collection names matched directly
    res1 = resolve_collection_scope("HISTORICAL", ["career_ledger", "feature_dna", "behavioral_dna", "long_term_wisdom"])
    assert res1 == ["career_ledger", "behavioral_dna", "feature_dna", "long_term_wisdom"], f"Mismatch in res1: {res1}"

    # Assertion 2: Single career_ledger
    res2 = resolve_collection_scope("HISTORICAL", ["career_ledger"])
    assert res2 == ["career_ledger"], f"Mismatch in res2: {res2}"

    # Assertion 3: Shorthand alias expansion
    res3 = resolve_collection_scope("TECHNICAL", ["bkm", "feature"])
    assert "behavioral_dna" in res3 and "feature_dna" in res3, f"Mismatch in res3: {res3}"

    # Assertion 4: Unmapped recovery via vibe priority
    res4 = resolve_collection_scope("HISTORICAL", ["completely_unmapped_custom_domain"])
    assert "career_ledger" in res4, f"Expected career_ledger in recovered scope: {res4}"

    # Assertion 5: Intentional empty target domains returns empty
    res5 = resolve_collection_scope("TECHNICAL", [])
    assert res5 == [], f"Expected empty list for explicit empty target_domains: {res5}"

    logger.info("✅ Probe 3.4.1 PASSED: All 5 scope resolution assertions satisfied.")
    return {"status": "PASS", "details": "Scope resolution and inclusive fallback validated."}


async def probe_3_4_2_archive_native_query() -> dict[str, Any]:
    """Probe 3.4.2: Archive node live Chroma query against career_ledger."""
    logger.info("🧪 Running Probe 3.4.2: Archive Node Live Chroma Query...")
    from nodes.archive_node import get_context

    raw = await get_context(
        query="Describe my RAS experience. Mailbox code. MCA. BERT HEST tables. What did I work on?",
        target_domains=["career_ledger", "feature_dna"],
        vibe="HISTORICAL",
        domain="work_history",
        n_results=3,
    )
    data = json.loads(raw)
    assert data.get("found") is True, f"get_context found=False: {data.get('reason')}"
    ctx = data.get("context", "")
    assert len(ctx) > 50, f"Context too short: {len(ctx)} chars"
    assert any(term in ctx.lower() for term in ["mailbox", "ras", "aep", "validation"]), "Context lacks expected career keywords"

    logger.info(f"✅ Probe 3.4.2 PASSED: Retrieved {len(ctx)} chars of authentic career context.")
    return {"status": "PASS", "context_length": len(ctx)}


def probe_3_4_3_turn_isolation() -> dict[str, Any]:
    """Probe 3.4.3: Turn isolation & anti-bleed hygiene."""
    logger.info("🧪 Running Probe 3.4.3: Turn Isolation & Anti-Bleed State Hygiene...")
    from logic.cognitive_hub import format_pacing_line

    # Assertion 1: Exhausted interest does NOT emit 0 tokens ceiling
    line_zero = format_pacing_line("pinky", 0.0)
    assert "Headroom ceiling is 0 tokens" not in line_zero, f"Forbidden 0 tokens ceiling emitted: {line_zero}"
    assert "brief" in line_zero.lower() or "exhausted" in line_zero.lower(), f"Unexpected exhausted format: {line_zero}"

    # Assertion 2: Positive interest scales nominally
    line_pos = format_pacing_line("brain", 0.5)
    assert "Headroom ceiling is 500 tokens" in line_pos, f"Unexpected scaled line: {line_pos}"

    logger.info("✅ Probe 3.4.3 PASSED: Anti-bleed and pacing directives verified.")
    return {"status": "PASS", "exhausted_directive": line_zero}


def extract_judge_score(event_id: str) -> Tuple[float, str]:
    """Extracts authoritative evaluation score from judge_backpressure.jsonl."""
    if not os.path.exists(JUDGE_BACKPRESSURE_PATH):
        return 0.0, "judge_backpressure.jsonl not found"

    matched = []
    with open(JUDGE_BACKPRESSURE_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or event_id not in line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("request_id") == event_id:
                    if entry.get("score_source") != "STUB" and entry.get("status") != "STANDBY_STUB":
                        matched.append(entry)
            except Exception:
                continue

    if not matched:
        return 0.0, f"No genuine judge record found for event {event_id}"

    # Prioritize Brain (Archive) RAG grounding evaluation score
    brain = [e for e in matched if "brain" in e.get("source", "").lower()]
    if brain:
        target = brain[-1]
        return float(target.get("score", 0.0)), target.get("critique") or target.get("status", "VERIFIED")

    pinky = [e for e in matched if "pinky" in e.get("source", "").lower()]
    if pinky:
        target = pinky[-1]
        return float(target.get("score", 0.0)), target.get("critique") or target.get("status", "VERIFIED")

    latest = matched[-1]
    return float(latest.get("score", 0.0)), latest.get("critique") or latest.get("status", "VERIFIED")


async def probe_3_4_4_live_silicon_replay(session: "aiohttp.ClientSession") -> dict[str, Any]:
    """Probe 3.4.4: Live silicon replay of Jason's 07:45 prompt against :8765."""
    prompt = "Describe my RAS experience. Mailbox code. MCA. BERT HEST tables. What did I work on?"
    logger.info(f"🚀 Running Probe 3.4.4: Injecting prompt into {FOYER_URL}/inject...")
    start = time.perf_counter()

    url = f"{FOYER_URL}/inject"
    payload = {"query": prompt, "source": "PROBE_PHASE3"}

    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
        if resp.status != 200:
            return {"status": "FAIL", "error": f"HTTP {resp.status} on /inject"}
        data = await resp.json()
        event_id = data.get("id")
        if not event_id:
            return {"status": "FAIL", "error": "No event ID returned by /inject"}

    logger.info(f"⏳ Injected turn {event_id}. Polling physical ledgers for completion...")
    stage_done = False
    max_wait = 90.0

    while (time.perf_counter() - start) < max_wait:
        if os.path.exists(STAGE_LEDGER_PATH):
            with open(STAGE_LEDGER_PATH, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    lower_line = line.lower()
                    if event_id in line and ("stage5" in lower_line or "stage_5" in lower_line or "pinky_voice" in lower_line or "deliberation_complete" in lower_line):
                        stage_done = True
                        break
        if stage_done:
            break
        await asyncio.sleep(2.0)

    elapsed_s = round(time.perf_counter() - start, 2)
    # Poll for Bonsai Judge async scoring to persist (LAN evaluation)
    score, critique = 0.0, "NO_RECORD"
    for _ in range(30):
        score, critique = extract_judge_score(event_id)
        if score > 0.0:
            break
        await asyncio.sleep(2.0)

    # Check journal ledger for Pinky's delivered response
    delivered_dialogue = ""
    if os.path.exists(os.path.join(DATA_DIR, "journal_ledger.jsonl")):
        with open(os.path.join(DATA_DIR, "journal_ledger.jsonl"), "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if prompt[:30] in line:
                    delivered_dialogue = line.strip()

    # Zero Telemetry Hallucination Assertion
    leak_keywords = ["silicon residency is active", "healthy thermal", "power metrics", "31°C", "33°C", "VRAM occupancy"]
    leak_found = [k for k in leak_keywords if k.lower() in delivered_dialogue.lower()]

    result = {
        "status": "PASS" if score >= 0.85 and not leak_found else "FAIL",
        "event_id": event_id,
        "elapsed_s": elapsed_s,
        "critic_score": score,
        "critique_summary": critique[:180] if critique else "None",
        "leak_detected": leak_found,
    }

    if result["status"] == "PASS":
        logger.info(f"✅ Probe 3.4.4 PASSED: Score={score}, 0 leaks detected, Turn completed in {elapsed_s}s.")
    else:
        logger.warning(f"❌ Probe 3.4.4 FAILED: Score={score}, Leaks={leak_found}")

    return result


async def main():
    logger.info("==================================================================")
    logger.info("🚀 PHASE 3 GAUNTLET: Scope Resolution, Native Chroma & Anti-Bleed")
    logger.info("==================================================================")

    r1 = probe_3_4_1_scope_resolution()
    r2 = await probe_3_4_2_archive_native_query()
    r3 = probe_3_4_3_turn_isolation()

    async with aiohttp.ClientSession() as session:
        r4 = await probe_3_4_4_live_silicon_replay(session)

    gauntlet = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "probe_3_4_1": r1,
        "probe_3_4_2": r2,
        "probe_3_4_3": r3,
        "probe_3_4_4": r4,
        "all_passed": all(r["status"] == "PASS" for r in [r1, r2, r3, r4]),
    }

    print("\n" + json.dumps(gauntlet, indent=2))
    sys.exit(0 if gauntlet["all_passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
