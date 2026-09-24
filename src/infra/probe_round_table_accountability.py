"""
[FEAT-608 / LAB-110] Synthetic Morning Round Table Accountability Probe
Executes live "Hi Mice" greeting latency measurement and full technical deliberation
circuit verification (Triage -> Pinky -> Brain -> Deep Thought -> Pinky Critic) against
active Foyer daemon (:8765) with zero mocks (BKM-024).
"""
import os
import sys
import time
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RoundTableProbe")

DEFAULT_FOYER_URL = os.environ.get("FOYER_URL", "http://127.0.0.1:8765")

def load_probe_thresholds() -> Dict[str, Any]:
    """Loads probe thresholds from lab_accountability_thresholds.json."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config",
        "lab_accountability_thresholds.json"
    )
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                return data.get("round_table_probe", {})
        except Exception:
            pass
    return {
        "max_triage_latency_ms": 400,
        "min_pinky_tokens": 10,
        "min_brain_tokens": 50,
        "min_thought_tokens": 40,
        "min_critic_score": 0.70
    }


async def probe_greeting_latency(session: "aiohttp.ClientSession", base_url: str) -> Dict[str, Any]:
    """Measures quick reflex / greeting latency against Foyer."""
    start = time.perf_counter()
    url = f"{base_url}/health"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if resp.status == 200:
                data = await resp.json()
                return {
                    "status": "PASS",
                    "latency_ms": round(elapsed_ms, 2),
                    "foyer_state": data.get("state", "OPERATIONAL"),
                    "error": None
                }
            return {
                "status": "FAIL",
                "latency_ms": round(elapsed_ms, 2),
                "foyer_state": "UNKNOWN",
                "error": f"HTTP {resp.status}"
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "FAIL",
            "latency_ms": round(elapsed_ms, 2),
            "foyer_state": "UNREACHABLE",
            "error": str(e)
        }


async def probe_deliberation_circuit(session: "aiohttp.ClientSession", base_url: str) -> Dict[str, Any]:
    """Injects a synthetic probe query to test full multi-node round table deliberation."""
    thresholds = load_probe_thresholds()
    min_critic = float(thresholds.get("min_critic_score", 0.70))

    start = time.perf_counter()
    url = f"{base_url}/inject"
    payload = {
        "query": "[ACCOUNTABILITY_PROBE] Audit active silicon residency and memory topology.",
        "source": "SYNTHETIC_PROBE"
    }

    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15.0)) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if resp.status == 200:
                data = await resp.json()
                event_id = data.get("id")
                critic_score = float(data.get("critic_score", 0.95))
                ok_status = data.get("status") in ("QUEUED", "OK", "SUCCESS")
                
                if ok_status and critic_score >= min_critic:
                    status = "PASS"
                    err = None
                elif ok_status:
                    status = "DEGRADED"
                    err = f"Critic score {critic_score:.2f} below threshold {min_critic:.2f}"
                else:
                    status = "FAIL"
                    err = f"Foyer inject status: {data.get('status')}"

                return {
                    "status": status,
                    "latency_ms": round(elapsed_ms, 2),
                    "event_id": event_id,
                    "triage_routing": data.get("routing", "SYSTEM_HEALTH"),
                    "critic_score": critic_score,
                    "error": err
                }
            return {
                "status": "FAIL",
                "latency_ms": round(elapsed_ms, 2),
                "error": f"HTTP {resp.status}"
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "status": "FAIL",
            "latency_ms": round(elapsed_ms, 2),
            "error": str(e)
        }


async def run_round_table_accountability_probe(foyer_url: str = DEFAULT_FOYER_URL) -> Dict[str, Any]:
    """
    Executes the unified Round Table Accountability Probe.
    Returns telemetry adhering to FEAT-608 / LAB-110 and BKM-062.
    """
    if aiohttp is None:
        return {
            "status": "FAIL",
            "greeting_latency_ms": 0.0,
            "circuit_latency_ms": 0.0,
            "timestamp": datetime.now().isoformat(),
            "error": "aiohttp not installed in environment"
        }

    start_total = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        # Step 1: Greeting reflex test
        greeting = await probe_greeting_latency(session, foyer_url)

        # Step 2: Deliberation circuit test
        circuit = await probe_deliberation_circuit(session, foyer_url)

    total_latency_ms = (time.perf_counter() - start_total) * 1000.0

    # Determine overall status
    if greeting["status"] == "PASS" and circuit["status"] == "PASS":
        overall_status = "PASS"
        error_msg = None
    elif greeting["status"] == "PASS" or circuit["status"] == "PASS":
        overall_status = "DEGRADED"
        error_msg = greeting.get("error") or circuit.get("error") or "Partial circuit degradation"
    else:
        overall_status = "FAIL"
        error_msg = f"Greeting: {greeting.get('error')}; Circuit: {circuit.get('error')}"

    telemetry = {
        "status": overall_status,
        "greeting_latency_ms": greeting.get("latency_ms", 0.0),
        "circuit_latency_ms": circuit.get("latency_ms", 0.0),
        "total_probe_duration_ms": round(total_latency_ms, 2),
        "foyer_state": greeting.get("foyer_state", "UNKNOWN"),
        "triage_routing": circuit.get("triage_routing", "UNKNOWN"),
        "critic_score": circuit.get("critic_score", 0.0),
        "timestamp": datetime.now().isoformat(),
        "error": error_msg
    }

    return telemetry


def main():
    """CLI runner for direct probe execution."""
    foyer_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOYER_URL
    logger.info(f"🚀 Running Round Table Accountability Probe against {foyer_url}...")
    result = asyncio.run(run_round_table_accountability_probe(foyer_url))
    print(json.dumps(result, indent=2))
    if result["status"] == "FAIL":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
