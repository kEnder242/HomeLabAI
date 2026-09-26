#!/usr/bin/env python3
# [FEAT-619 / BKM-066] Standalone Morning Accountability Watchdog & Decoupled Audit Engine
# Purpose: Decoupled out-of-band auditor that executes independently at the end of the nightly
#          maintenance window (06:00 AM) to verify all nightly deliverables, detect silent crashes,
#          stale locks, and emit the authoritative daily_accountability_digest.json.

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent  # HomeLabAI/src/infra
SRC_DIR = BASE_DIR.parent                   # HomeLabAI/src
HOMELAB_DIR = SRC_DIR.parent                # HomeLabAI
LAB_ROOT = HOMELAB_DIR.parent               # Dev_Lab
CONFIG_DIR = HOMELAB_DIR / "config"
RUN_DIR = HOMELAB_DIR / "run"
THRESHOLDS_PATH = CONFIG_DIR / "lab_accountability_thresholds.json"
OUTPUT_DIR = LAB_ROOT / "Portfolio_Dev" / "field_notes" / "data"
WWW_DEPLOY_DIR = LAB_ROOT / "www_deploy" / "data"
DIGEST_FILE = "daily_accountability_digest.json"

NIGHTLY_FORGE_STATE = RUN_DIR / "nightly_forge_state.json"
NIGHTLY_LORA_STATE = RUN_DIR / "nightly_lora_training_state.json"
MAINTENANCE_LOCK = RUN_DIR / "maintenance.lock"
FORGE_LOCK = RUN_DIR / "nightly_forge.lock"
LORA_LOCK = RUN_DIR / "nightly_lora_training.lock"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ACCOUNTABILITY_WATCHDOG] %(message)s"
)
logger = logging.getLogger("accountability_watchdog")

try:
    from infra.pager_relay import trigger_pager
except ImportError:
    try:
        from src.infra.pager_relay import trigger_pager
    except ImportError:
        def trigger_pager(message, severity="INFO", source="System"):
            pass


def load_thresholds():
    """Load configurable metric thresholds."""
    if THRESHOLDS_PATH.exists():
        try:
            return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not read thresholds from {THRESHOLDS_PATH}: {e}")
    return {}


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently active."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def check_gpu_power_clamp():
    """Check 1: Live GPU Power Limit Verification (<= max_watts)."""
    thresholds = load_thresholds()
    max_watts = float(thresholds.get("gpu_power_clamp", {}).get("max_watts", 170.0))
    target_watts = float(thresholds.get("gpu_power_clamp", {}).get("target_watts", 165.0))
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.limit", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            val = float(res.stdout.strip().split("\n")[0])
            passed = val <= max_watts
            return {
                "name": f"GPU Power Clamp ({int(target_watts)}W)",
                "passed": passed,
                "detail": f"Power limit is {val:.1f}W (max {max_watts:.1f}W)" if passed else f"Power limit {val:.1f}W exceeds {max_watts:.1f}W threshold",
                "val": val
            }
    except Exception as e:
        logger.warning(f"GPU check failed: {e}")
    return {
        "name": f"GPU Power Clamp ({int(target_watts)}W)",
        "passed": False,
        "detail": "Failed to query nvidia-smi power limit",
        "val": None
    }


def check_foyer_and_vram():
    """Check 2: Foyer & vLLM Service Liveness."""
    foyer_ok = False
    detail = "Foyer unreachable"
    try:
        req = urllib.request.Request("http://127.0.0.1:8765/status?timeout=1", headers={"User-Agent": "Watchdog"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                status = data.get("status", "UNKNOWN")
                state = data.get("state", "UNKNOWN")
                engine_up = bool(data.get("engine_up", False))
                # Must be operational with active silicon engine to pass morning liveness
                foyer_ok = engine_up and (status in ("OPERATIONAL", "ONLINE", "WAKING") or state in ("OPERATIONAL", "ONLINE", "WAKING"))
                detail = f"Foyer state: {state}, status: {status}, engine: {'UP' if engine_up else 'STANDBY/DOWN'}"
    except Exception as e:
        detail = f"Foyer error: {e}"

    return {
        "name": "Foyer Re-Ignition & Hot-Reload",
        "passed": foyer_ok,
        "detail": detail
    }


def check_stale_locks():
    """Check 3: Stale Lock & Crash Sentry with PID Liveness Verification."""
    stale_found = []
    for lock_path in [MAINTENANCE_LOCK, FORGE_LOCK, LORA_LOCK]:
        if lock_path.exists():
            age_s = time.time() - lock_path.stat().st_mtime
            pid_alive = False
            lock_pid = None
            try:
                content = lock_path.read_text(encoding="utf-8").strip()
                if content and content.isdigit():
                    lock_pid = int(content)
                    pid_alive = is_pid_alive(lock_pid)
            except Exception:
                pass

            if age_s > 1800:  # 30+ minutes old
                if lock_pid and not pid_alive:
                    stale_found.append(f"{lock_path.name} (DEAD PID {lock_pid}, {age_s/60:.1f}m old)")
                else:
                    stale_found.append(f"{lock_path.name} ({age_s/60:.1f}m old)")

    passed = len(stale_found) == 0
    return {
        "name": "Lockfile Cleanliness & Quiescence",
        "passed": passed,
        "detail": "All lockfiles cleared" if passed else f"Stale lock(s) detected: {', '.join(stale_found)}"
    }


def check_nightly_forge_liveness():
    """Check 4: Nightly Forge Execution Liveness & Completion Status."""
    if not NIGHTLY_FORGE_STATE.exists():
        return {
            "name": "Nightly Forge Orchestration",
            "passed": False,
            "detail": "State file missing (nightly_forge never ran)",
            "status": "MISSING"
        }
    try:
        state = json.loads(NIGHTLY_FORGE_STATE.read_text(encoding="utf-8"))
        status = state.get("status", "UNKNOWN")
        last_ts = state.get("last_completed_timestamp", 0)
        age_hours = (time.time() - last_ts) / 3600.0 if last_ts else 999.0
        
        passed = (status == "COMPLETED") and (age_hours < 26.0)
        return {
            "name": "Nightly Forge Orchestration",
            "passed": passed,
            "detail": f"Status: {status} (Age: {age_hours:.1f}h)",
            "status": status,
            "age_hours": round(age_hours, 1)
        }
    except Exception as e:
        return {
            "name": "Nightly Forge Orchestration",
            "passed": False,
            "detail": f"Failed to parse state: {e}",
            "status": "CORRUPTED"
        }


def check_lora_training():
    """Check 5: LoRA Fine-Tuning Multi-Adapter Pass."""
    if not NIGHTLY_LORA_STATE.exists():
        return {
            "name": "LoRA Fine-Tuning Multi-Adapter Pass",
            "passed": False,
            "detail": "LoRA state file missing",
            "status": "MISSING"
        }
    try:
        state = json.loads(NIGHTLY_LORA_STATE.read_text(encoding="utf-8"))
        status = state.get("status", "UNKNOWN")
        passed = status in ("COMPLETED", "SUCCESS")
        return {
            "name": "LoRA Fine-Tuning Multi-Adapter Pass",
            "passed": passed,
            "detail": f"Status: {status}",
            "status": status
        }
    except Exception as e:
        return {
            "name": "LoRA Fine-Tuning Multi-Adapter Pass",
            "passed": False,
            "detail": f"Failed to parse LoRA state: {e}",
            "status": "CORRUPTED"
        }


def check_subconscious_dreaming():
    """Check 6: Accountable Subconscious Dreaming & Gem Refinement."""
    gems_path = OUTPUT_DIR / "latest_synthesis_gems.json"
    if not gems_path.exists():
        return {
            "name": "Accountable Subconscious Dreaming",
            "passed": False,
            "detail": "No gems file found",
            "count": 0
        }
    try:
        data = json.loads(gems_path.read_text(encoding="utf-8"))
        gems = data if isinstance(data, list) else data.get("gems", [])
        passed = len(gems) > 0
        return {
            "name": "Accountable Subconscious Dreaming",
            "passed": passed,
            "detail": f"Active Gems: {len(gems)}",
            "count": len(gems)
        }
    except Exception as e:
        return {
            "name": "Accountable Subconscious Dreaming",
            "passed": False,
            "detail": f"Gems parse error: {e}",
            "count": 0
        }


def check_morning_round_table(run_live: bool = True):
    """Check 7: Synthetic Morning Round Table Accountability Probe."""
    if run_live:
        try:
            probe_script = BASE_DIR / "probe_round_table_accountability.py"
            if probe_script.exists():
                res = subprocess.run(
                    [sys.executable, str(probe_script)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if res.returncode == 0 and res.stdout.strip():
                    try:
                        m = re.search(r'\{[\s\S]*\}', res.stdout)
                        if m:
                            probe_data = json.loads(m.group(0))
                            status = probe_data.get("status", "FAIL")
                            score = float(probe_data.get("critic_score", 0.0))
                            passed = (status == "PASS") and (score >= 0.70)
                            return {
                                "name": "Synthetic Morning Round Table Probe",
                                "passed": passed,
                                "detail": f"Status: {status}, Critic Score: {score:.2f}, Latency: {probe_data.get('greeting_latency_ms', 0)}ms",
                                "critic_score": score
                            }
                    except Exception as parse_err:
                        logger.warning(f"Probe JSON parse failed: {parse_err}")
        except Exception as e:
            logger.warning(f"Live round table probe failed: {e}")

    # Fallback to checking previous digest probe record if live execution skipped
    return {
        "name": "Synthetic Morning Round Table Probe",
        "passed": False,
        "detail": "Round Table Probe failed or timed out",
        "critic_score": 0.0
    }


def audit_and_emit_digest(run_live_probe: bool = True):
    """Run full decoupled accountability audit and write digest JSON."""
    checks = []
    discrepancies = []

    # Run checks
    c_gpu = check_gpu_power_clamp()
    checks.append(c_gpu)
    if not c_gpu["passed"]:
        discrepancies.append(c_gpu["detail"])

    c_vram = check_foyer_and_vram()
    checks.append(c_vram)
    if not c_vram["passed"]:
        discrepancies.append(c_vram["detail"])

    c_lock = check_stale_locks()
    checks.append(c_lock)
    if not c_lock["passed"]:
        discrepancies.append(c_lock["detail"])

    c_forge = check_nightly_forge_liveness()
    checks.append(c_forge)
    if not c_forge["passed"]:
        discrepancies.append(f"Nightly Forge did not complete successfully ({c_forge['detail']})")

    c_lora = check_lora_training()
    checks.append(c_lora)
    if not c_lora["passed"]:
        discrepancies.append(f"LoRA Multi-Adapter Pass failed ({c_lora['detail']})")

    c_dream = check_subconscious_dreaming()
    checks.append(c_dream)
    if not c_dream["passed"]:
        discrepancies.append(c_dream["detail"])

    c_probe = check_morning_round_table(run_live=run_live_probe)
    checks.append(c_probe)
    if not c_probe["passed"]:
        discrepancies.append(c_probe["detail"])

    # Determine overall status
    passed_count = sum(1 for c in checks if c["passed"])
    total_count = len(checks)
    critical_failed = (not c_forge["passed"]) or (not c_lora["passed"]) or (not c_vram["passed"])

    if passed_count == total_count:
        overall_status = "PASS"
    elif critical_failed:
        overall_status = "FAIL"
    else:
        overall_status = "DEGRADED"

    digest = {
        "timestamp": datetime.datetime.now().isoformat(),
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "auditor": "standalone_accountability_watchdog (FEAT-619)",
        "overall_status": overall_status,
        "total_checks": total_count,
        "passed_checks": passed_count,
        "failed_checks": total_count - passed_count,
        "checks": checks,
        "discrepancies": discrepancies,
    }

    # Write digest to output locations with atomic fsync
    for target_dir in [OUTPUT_DIR, WWW_DEPLOY_DIR]:
        target_dir.mkdir(parents=True, exist_ok=True)
        out_file = target_dir / DIGEST_FILE
        tmp_file = target_dir / f"{DIGEST_FILE}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(digest, indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, out_file)
            logger.info(f"✅ Wrote authoritative digest to {out_file} (Status: {overall_status})")
        except Exception as e:
            logger.error(f"Failed to write digest to {out_file}: {e}")

    # Broadcast Neural Pager / Alert
    if overall_status != "PASS":
        trigger_pager(
            f"[ACCOUNTABILITY AUDIT: {overall_status}] {passed_count}/{total_count} checks passed. Discrepancies: {'; '.join(discrepancies[:2])}",
            severity="ERROR" if overall_status == "FAIL" else "WARNING",
            source="AccountabilityWatchdog"
        )

    return digest


def main():
    parser = argparse.ArgumentParser(description="Standalone Morning Accountability Watchdog (FEAT-619)")
    parser.add_argument("--no-probe", action="store_true", help="Skip live synthetic morning round table probe")
    parser.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    args = parser.parse_args()

    digest = audit_and_emit_digest(run_live_probe=not args.no_probe)
    if args.json:
        print(json.dumps(digest, indent=2))
    else:
        print("\n=== MORNING ACCOUNTABILITY AUDIT REPORT ===")
        print(f"Status:        {digest['overall_status']}")
        print(f"Checks Passed: {digest['passed_checks']}/{digest['total_checks']}")
        for c in digest["checks"]:
            mark = "✅" if c["passed"] else "❌"
            print(f"  {mark} {c['name']}: {c['detail']}")
        if digest["discrepancies"]:
            print("\n🚨 DISCREPANCIES DETECTED:")
            for d in digest["discrepancies"]:
                print(f"  - {d}")

    # Explicit exit status signaling for supervisor / systemd / CI gates
    if digest["overall_status"] == "FAIL":
        sys.exit(1)
    elif digest["overall_status"] == "DEGRADED":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

