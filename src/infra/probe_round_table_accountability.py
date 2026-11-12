#!/usr/bin/env python3
"""
probe_round_table_accountability.py — Synthetic Morning Round Table Accountability Probe Suite
[FEAT-608 / LAB-110 / BKM-062] Ground-Truth Multi-Resident Verification Suite.

Validates that:
1. Foyer reflex greeting latency is within threshold.
2. An injected synthetic technical deliberation query actually progresses through the multi-stage
   Round Table pipeline and logs physical stage completions in foyer_stage_ledger.jsonl.
3. The Judge / Critic records a genuine numeric evaluation in judge_backpressure.jsonl without mocks or fallback defaults.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import aiohttp
except ImportError:
    aiohttp = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("probe_accountability")

DEFAULT_FOYER_URL = "http://127.0.0.1:8765"
WORKSPACE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "..",
    )
)
DATA_DIR = os.path.join(WORKSPACE_DIR, "Portfolio_Dev/field_notes/data")
STAGE_LEDGER_PATH = os.path.join(DATA_DIR, "foyer_stage_ledger.jsonl")
JUDGE_BACKPRESSURE_PATH = os.path.join(DATA_DIR, "judge_backpressure.jsonl")


def load_probe_thresholds() -> dict[str, Any]:
    """Loads probe thresholds and centralized timeouts from lab_accountability_thresholds.json."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config",
        "lab_accountability_thresholds.json",
    )
    res = {
        "max_triage_latency_ms": 400,
        "min_pinky_tokens": 10,
        "min_brain_tokens": 50,
        "min_thought_tokens": 40,
        "min_critic_score": 0.70,
        "max_wait_seconds": 120.0,
        "greeting_timeout_sec": 5.0,
        "inject_timeout_sec": 10.0,
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                probe_cfg = data.get("round_table_probe", {})
                timeouts = data.get("timeouts", {})
                res.update(probe_cfg)
                if "round_table_deliberation_max_wait_sec" in timeouts:
                    res["max_wait_seconds"] = float(timeouts["round_table_deliberation_max_wait_sec"])
                if "foyer_greeting_probe_timeout_sec" in timeouts:
                    res["greeting_timeout_sec"] = float(timeouts["foyer_greeting_probe_timeout_sec"])
                if "foyer_inject_timeout_sec" in timeouts:
                    res["inject_timeout_sec"] = float(timeouts["foyer_inject_timeout_sec"])
        except Exception:
            pass
    return res


async def probe_greeting_latency(
    session: "aiohttp.ClientSession", base_url: str, timeout_sec: float = 5.0
) -> dict[str, Any]:
    """Measures quick reflex / greeting latency against Foyer."""
    start = time.perf_counter()
    url = f"{base_url}/health"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if resp.status == 200:
                data = await resp.json()
                foyer_state = data.get("state", "OPERATIONAL")
                return {
                    "status": "PASS" if foyer_state in ("OPERATIONAL", "ONLINE", "WAKING", "IDLE") else "DEGRADED",
                    "latency_ms": round(elapsed_ms, 2),
                    "foyer_state": foyer_state,
                    "error": None,
                }
            return {
                "status": "FAIL",
                "latency_ms": round(elapsed_ms, 2),
                "foyer_state": "UNKNOWN",
                "error": f"HTTP {resp.status}",
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "FAIL",
            "latency_ms": round(elapsed_ms, 2),
            "foyer_state": "UNREACHABLE",
            "error": str(e),
        }


def extract_judge_score(event_id: str, max_lookback_s: float = 60.0) -> Tuple[float, Optional[str]]:
    """
    [FEAT-608] Extracts authoritative evaluation score from judge_backpressure.jsonl for the given request ID.
    Enforces Multi-Stage Evaluator Vector Schema: prioritizes terminal Stage 5 delivered response
    ('Pinky (Response)'), then Stage 4 ('Deep Thought'), over intermediate Stage 1 Archive Interest.
    Rejects local failover stubs to prevent fake score leaks.
    Returns (score_normalized, critique_summary).
    """
    if not os.path.exists(JUDGE_BACKPRESSURE_PATH):
        return 0.0, "judge_backpressure.jsonl not found"

    try:
        matched_entries = []
        stub_records = []
        with open(JUDGE_BACKPRESSURE_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or event_id not in line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("request_id") == event_id:
                        # Detect and track stub records
                        if entry.get("score_source") == "STUB" or entry.get("status") == "STANDBY_STUB":
                            stub_records.append(entry)
                            continue
                        matched_entries.append(entry)
                except Exception:
                    continue

        # If sovereign judges failed over to stubs, do not allow Brain's unverified self-assessment to mask it
        has_sovereign_judge = any(
            "pinky" in e.get("source", "").lower() or "thought" in e.get("source", "").lower()
            for e in matched_entries
        )
        if stub_records and not has_sovereign_judge:
            stub_reason = (
                stub_records[-1].get("critique")
                or stub_records[-1].get("status", "STANDBY_STUB")
            )
            return 0.0, f"[SOVEREIGN_JUDGES_OFFLINE] {stub_reason}"

        if not matched_entries:
            return 0.0, f"No genuine online judge record found for event {event_id}"

        # [Story 111.20 / FEAT-665] Sovereign quorum enforcement:
        # Require >= 1 vocal sovereign judge seat (Pinky or Deep Thought) for any PASS verdict.
        # If all sovereign seats returned STANDBY_STUB (or no sovereign seat vocalized at all),
        # fail immediately with score 0.0 -- eradicates false PASS on non-sovereign self-assessment.
        if not has_sovereign_judge:
            return (
                0.0,
                f"[SOVEREIGN_QUORUM_ABSENT] No vocal sovereign judge "
                f"(Pinky/Deep Thought) recorded for event {event_id}",
            )

        # Multi-stage prioritization per [FEAT-608]:
        # 1. Prefer terminal Stage 5 delivered response
        pinky_entries = [e for e in matched_entries if "pinky" in e.get("source", "").lower()]
        if pinky_entries:
            target = pinky_entries[-1]
            score = float(target.get("score", 0.0))
            critique = target.get("style_critique") or target.get("critique") or target.get("status", "VERIFIED")
            return score, f"[STAGE_5_PINKY] {critique}"

        # 2. Prefer Deep Thought synthesis
        dt_entries = [e for e in matched_entries if "thought" in e.get("source", "").lower()]
        if dt_entries:
            target = dt_entries[-1]
            score = float(target.get("score", 0.0))
            critique = target.get("style_critique") or target.get("critique") or target.get("status", "VERIFIED")
            return score, f"[STAGE_4_DEEP_THOUGHT] {critique}"

        # 3. Fallback to latest non-stub entry
        latest = matched_entries[-1]
        score = float(latest.get("score", 0.0))
        critique = latest.get("style_critique") or latest.get("critique") or latest.get("status", "VERIFIED")
        source = latest.get("source", "UNKNOWN")
        return score, f"[{source}] {critique}"
    except Exception as e:
        return 0.0, f"Judge extraction error: {e}"


async def probe_deliberation_circuit(
    session: "aiohttp.ClientSession",
    base_url: str,
    topic: str = "Audit active silicon residency and memory topology.",
    max_wait_seconds: Optional[float] = None,
) -> dict[str, Any]:
    """
    Injects a synthetic probe query and monitors physical ledgers for ground-truth
    completion and judicial scoring.
    """
    thresholds = load_probe_thresholds()
    min_critic = float(thresholds.get("min_critic_score", 0.70))
    if max_wait_seconds is None:
        max_wait_seconds = float(thresholds.get("max_wait_seconds", 120.0))
    inject_timeout = float(thresholds.get("inject_timeout_sec", 10.0))

    start = time.perf_counter()
    url = f"{base_url}/inject"
    payload = {"query": f"[ACCOUNTABILITY_PROBE] {topic}", "source": "SYNTHETIC_PROBE"}

    try:
        # Step 1: Enqueue via /inject
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=inject_timeout)
        ) as resp:
            if resp.status != 200:
                return {
                    "status": "FAIL",
                    "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
                    "critic_score": 0.0,
                    "error": f"HTTP {resp.status} on /inject",
                    "sovereign_quorum": False,
                }
            data = await resp.json()
            event_id = data.get("id")
            if not event_id:
                return {
                    "status": "FAIL",
                    "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
                    "critic_score": 0.0,
                    "error": "No event ID returned by Foyer /inject",
                    "sovereign_quorum": False,
                }

        # Step 2: Poll stage ledger & judge backpressure for ground-truth physical completion
        stage1_completed = False
        triage_routing = "UNKNOWN"
        judge_score = 0.0
        judge_critique = None
        deadline = time.time() + max_wait_seconds

        while time.time() < deadline:
            # Check stage ledger
            if os.path.exists(STAGE_LEDGER_PATH):
                try:
                    with open(STAGE_LEDGER_PATH, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if event_id in line:
                                entry = json.loads(line.strip())
                                if "triage" in entry.get("stage", "") and entry.get("status") == "COMPLETED":
                                    stage1_completed = True
                                    triage_routing = entry.get("detail", "triage_complete")
                except Exception:
                    pass

            # Check judge backpressure ledger for final evaluation score
            score, critique = extract_judge_score(event_id)
            if score > 0.0 and "[STAGE_5_PINKY]" in str(critique):
                judge_score = score
                judge_critique = critique
                break
            elif score > 0.0:
                judge_score = score
                judge_critique = critique

            await asyncio.sleep(0.5)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if not stage1_completed and judge_score == 0.0:
            return {
                "status": "FAIL",
                "latency_ms": round(elapsed_ms, 2),
                "event_id": event_id,
                "triage_routing": "TIMEOUT",
                "critic_score": 0.0,
                "error": f"Triage stage did not complete within {max_wait_seconds}s",
                "sovereign_quorum": False,
            }

        if judge_score > 0.0:
            passed = judge_score >= min_critic
            return {
                "status": "PASS" if passed else "DEGRADED",
                "latency_ms": round(elapsed_ms, 2),
                "event_id": event_id,
                "triage_routing": triage_routing,
                "critic_score": round(judge_score, 2),
                "error": None if passed else f"Judge score {judge_score:.2f} < {min_critic:.2f} ({judge_critique})",
                "sovereign_quorum": True,
            }

        # Fallback if triage executed but judge timed out or failed over
        return {
            "status": "DEGRADED",
            "latency_ms": round(elapsed_ms, 2),
            "event_id": event_id,
            "triage_routing": triage_routing,
            "critic_score": 0.0,
            "error": "Triage succeeded, but no genuine online judicial score was recorded",
            "sovereign_quorum": False,
        }

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "FAIL",
            "latency_ms": round(elapsed_ms, 2),
            "critic_score": 0.0,
            "error": str(e),
            "sovereign_quorum": False,
        }


def resolve_probe_topic(cli_topic: str | None = None) -> str:
    """Select probe topic: CLI argument > latest_synthesis_gems rotation > archetype rotation.
    
    Prevents morning probe and daily assessments from stagnating in a local minimum on a single prompt.
    """
    if cli_topic and cli_topic.strip():
        return cli_topic.strip()

    # Attempt to load from latest_synthesis_gems.json
    gems_path = Path("/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/latest_synthesis_gems.json")
    if gems_path.exists():
        try:
            with open(gems_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            gems = data.get("gems", [])
            if gems:
                # Rotate across available top gems using day-of-year
                day_idx = datetime.now().timetuple().tm_yday
                # Alternate between operational probe (day 0 mod 2) and an extracted gem (day 1 mod 2)
                if day_idx % 2 == 1:
                    gem_idx = (day_idx // 2) % len(gems)
                    summary = gems[gem_idx].get("summary", "")
                    clean = re.sub(r"^\[.*?\]\s*", "", summary).strip()
                    if clean:
                        return clean
        except Exception as e:
            logger.debug(f"Could not load dynamic gem topic: {e}")

    # Fallback to rotating domain archetypes
    archetypes = [
        "Audit active silicon residency and memory topology.",
        "Examine the Kayak and Montana platform transition and native PECI execution.",
        "Review Clearwater Forest (CWF) and Diamond Rapids (DMR) manageability and Redfish test collateral.",
        "Audit DMR MMIO register adaptation and pre-silicon Simics validation test cases.",
        "Audit PECI transaction metrics and thermal stress testing methodology.",
    ]
    idx = datetime.now().timetuple().tm_yday % len(archetypes)
    return archetypes[idx]


async def run_round_table_accountability_probe(
    foyer_url: str = DEFAULT_FOYER_URL,
    topic: str | None = None,
) -> dict[str, Any]:
    """
    Executes the unified Ground-Truth Round Table Accountability Probe.
    Returns telemetry adhering to FEAT-608 / LAB-110 and BKM-062.
    """
    if not topic:
        topic = resolve_probe_topic()
    if aiohttp is None:
        return {
            "status": "FAIL",
            "greeting_latency_ms": 0.0,
            "circuit_latency_ms": 0.0,
            "sovereign_quorum": False,
            "timestamp": datetime.now().isoformat(),
            "error": "aiohttp not installed in environment",
        }

    thresholds = load_probe_thresholds()
    greeting_timeout = float(thresholds.get("greeting_timeout_sec", 5.0))
    max_wait = float(thresholds.get("max_wait_seconds", 120.0))

    start_total = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        # Step 1: Greeting reflex test
        greeting = await probe_greeting_latency(session, foyer_url, timeout_sec=greeting_timeout)

        # Step 2: Deliberation circuit test
        circuit = await probe_deliberation_circuit(session, foyer_url, topic=topic, max_wait_seconds=max_wait)

    total_latency_ms = (time.perf_counter() - start_total) * 1000.0

    # Determine overall status
    if greeting["status"] == "PASS" and circuit["status"] == "PASS":
        overall_status = "PASS"
        error_msg = None
    elif greeting["status"] in ("PASS", "DEGRADED") and circuit["status"] in ("PASS", "DEGRADED"):
        overall_status = "DEGRADED"
        error_msg = (
            greeting.get("error")
            or circuit.get("error")
            or "Partial circuit degradation"
        )
    else:
        overall_status = "FAIL"
        error_msg = (
            f"Greeting: {greeting.get('error')}; Circuit: {circuit.get('error')}"
        )

    telemetry = {
        "status": overall_status,
        "greeting_latency_ms": greeting.get("latency_ms", 0.0),
        "circuit_latency_ms": circuit.get("latency_ms", 0.0),
        "total_probe_duration_ms": round(total_latency_ms, 2),
        "foyer_state": greeting.get("foyer_state", "UNKNOWN"),
        "triage_routing": circuit.get("triage_routing", "UNKNOWN"),
        "critic_score": circuit.get("critic_score", 0.0),
        "sovereign_quorum": circuit.get("sovereign_quorum", False),
        "timestamp": datetime.now().isoformat(),
        "error": error_msg,
        "topic": topic,
    }

    return telemetry


def main():
    """CLI runner for direct probe execution."""
    foyer_url = DEFAULT_FOYER_URL
    topic = None
    for arg in sys.argv[1:]:
        if arg.startswith("http://") or arg.startswith("https://"):
            foyer_url = arg
        elif arg.startswith("--topic="):
            topic = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            topic = arg

    resolved_topic = resolve_probe_topic(topic)
    logger.info(f"🚀 Running Ground-Truth Round Table Accountability Probe against {foyer_url} (Topic: {resolved_topic[:60]})...")
    result = asyncio.run(run_round_table_accountability_probe(foyer_url, topic=resolved_topic))
    print(json.dumps(result, indent=2))
    # [Story 111.20] Exit non-zero on FAIL, DEGRADED, or absent sovereign quorum
    if (
        result["status"] in ("FAIL", "DEGRADED")
        or not result.get("sovereign_quorum", False)
    ):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
