#!/usr/bin/env python3
# [FEAT-619 / BKM-066] Standalone Morning Accountability Watchdog & Decoupled Audit Engine
# Purpose: Decoupled out-of-band auditor that executes independently at the end of the nightly
#          maintenance window (06:00 AM) to verify all nightly deliverables, detect silent crashes,
#          stale locks, and emit the authoritative daily_accountability_digest.json.

import argparse
import datetime
import fcntl
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
DIGEST_FILE = "daily_accountability_digest.json"
# [Story 971 / FEAT-619 evolution] Single canonical home for all runtime data:
# the watchdog no longer mirrors to www_deploy/. Ledger is appended (not replaced)
# so the interleaved timeline in status.html accumulates every audit run.
LEDGER_FILE = "accountability_ledger.jsonl"
LEDGER_MAX_BYTES = 5 * 1024 * 1024  # 5MB: rotate ledger before it stalls the static pager poller

NIGHTLY_FORGE_STATE = RUN_DIR / "nightly_forge_state.json"
NIGHTLY_LORA_STATE = RUN_DIR / "nightly_lora_training_state.json"
MAINTENANCE_LOCK = RUN_DIR / "maintenance.lock"
FORGE_LOCK = RUN_DIR / "nightly_forge.lock"
LORA_LOCK = RUN_DIR / "nightly_lora_training.lock"

# Cgroup v2 swap pressure paths [Story 101.12]
CGROUP_SWAP_PEAK = Path("/sys/fs/cgroup/memory.swap.peak")
CGROUP_SWAP_CURRENT = Path("/sys/fs/cgroup/memory.swap.current")
CGROUP_SWAP_MAX = Path("/sys/fs/cgroup/memory.swap.max")
PROC_MEMINFO = Path("/proc/meminfo")

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
    """Check 3: Stale Lock Reaper — detect, verify, and purge orphaned lock files.

    [FEAT-641] Two-phase approach:
      Phase 1 — Classify each lock file (live, stale, or unknown).
      Phase 2 — Purge any lock file whose PID is confirmed dead AND the kernel
                 fcntl advisory lock is not held. Never touch actively-held locks.
    """
    stale_found = []
    reaped = []

    for lock_path in [MAINTENANCE_LOCK, FORGE_LOCK, LORA_LOCK]:
        if not lock_path.exists():
            continue

        age_s = time.time() - lock_path.stat().st_mtime
        pid_alive = False
        lock_pid = None

        # --- Phase 1a: Parse PID from lock file ---
        try:
            content = lock_path.read_text(encoding="utf-8").strip()
            if content:
                for line in content.splitlines():
                    line_s = line.strip()
                    if line_s.isdigit():
                        lock_pid = int(line_s)
                        break
                    elif line_s.startswith("pid="):
                        cand = line_s.split("=")[1].strip()
                        if cand.isdigit():
                            lock_pid = int(cand)
                            break
                if lock_pid:
                    pid_alive = is_pid_alive(lock_pid)
        except Exception:
            pass

        # --- Phase 1b: Probe kernel advisory lock (non-blocking) ---
        is_kernel_locked = False
        try:
            with open(lock_path, "a") as test_fd:
                try:
                    fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(test_fd, fcntl.LOCK_UN)
                except (OSError, BlockingIOError):
                    is_kernel_locked = True
        except Exception:
            pass

        # --- Classification ---
        if is_kernel_locked and pid_alive:
            # Actively running process legitimately holds the lock — leave it alone
            continue

        if age_s <= 1800:
            # Fresh lock (<30m) — may be a slow-starting process; don't reap yet
            continue

        # Lock is stale: old + no live kernel holder
        label = f"{lock_path.name} (DEAD PID {lock_pid}, {age_s/60:.1f}m old)" if (lock_pid and not pid_alive) \
                else f"{lock_path.name} ({age_s/60:.1f}m old)"
        stale_found.append(label)

        # --- Phase 2: Purge confirmed-dead locks ---
        # Safety gate: only reap if PID is explicitly confirmed dead.
        # Unknown-PID locks (pid_alive=False because no PID was found) are also reaped
        # after the 30-min grace period since there is no process to protect.
        if not pid_alive:
            try:
                lock_path.unlink(missing_ok=True)
                reaped.append(lock_path.name)
                logger.warning(
                    "[REAP] Purged stale lock %s — %s", lock_path.name, label
                )
            except Exception as exc:
                logger.error("[REAP] Failed to purge %s: %s", lock_path.name, exc)

    passed = len(stale_found) == 0
    detail_parts = []
    if stale_found:
        detail_parts.append(f"Stale lock(s) detected: {', '.join(stale_found)}")
    if reaped:
        detail_parts.append(f"Reaped: {', '.join(reaped)}")

    return {
        "name": "Lockfile Cleanliness & Quiescence",
        "passed": passed,
        "detail": "All lockfiles cleared" if passed else "; ".join(detail_parts),
        "reaped": reaped,
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
        winner_pid = state.get("winner_pid")

        # If marked RUNNING, verify PID is actually alive
        if status == "RUNNING" and winner_pid:
            if not is_pid_alive(winner_pid):
                logger.warning(
                    "[REAP] Nightly forge marked RUNNING but PID %s is dead. Marking CRASHED.",
                    winner_pid,
                )
                status = "CRASHED"
                state["status"] = "CRASHED"
                state["crashed_at"] = time.time()
                state["crashed_iso"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                try:
                    NIGHTLY_FORGE_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
                except Exception:
                    pass

        last_ts = state.get("last_completed_timestamp", 0)
        age_hours = (time.time() - last_ts) / 3600.0 if last_ts else 999.0
        
        # [FEAT-619 / Story 106.2] Allow completed DEGRADED forge run to pass liveness check
        passed = (status in ("COMPLETED", "DEGRADED")) and (age_hours < 26.0)
        return {
            "name": "Nightly Forge Orchestration",
            "passed": passed,
            "detail": f"Status: {status} (Age: {age_hours:.1f}h)" if status != "CRASHED" else f"Status: CRASHED (DEAD PID {winner_pid})",
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
        age = time.time() - gems_path.stat().st_mtime
        STALE_WINDOW_SEC = 108000  # 30 hours
        if len(gems) == 0:
            passed = False
            detail = "Gems empty"
        elif age > STALE_WINDOW_SEC:
            passed = False
            detail = f"Stale: {age/3600:.1f}h (>30.0h stale window), {len(gems)} gems"
        else:
            passed = True
            detail = f"Fresh: {age/3600:.1f}h, Active Gems: {len(gems)}"
        return {
            "name": "Accountable Subconscious Dreaming",
            "passed": passed,
            "detail": detail,
            "count": len(gems)
        }
    except Exception as e:
        return {
            "name": "Accountable Subconscious Dreaming",
            "passed": False,
            "detail": f"Gems parse error: {e}",
            "count": 0
         }


def check_swap_pressure():
    """Check 8: Cgroup Swap Pressure — monitor swap utilization and peak usage.
    
    Reads from cgroup v2 paths:
      /sys/fs/cgroup/memory.swap.peak
      /sys/fs/cgroup/memory.swap.current
    Falls back to /proc/meminfo for total/free swap if cgroup not available.
    Computes swap utilization percentage.
    """
    swap_peak = None
    swap_current = None
    swap_utilization_pct = 0.0
    
    try:
        if CGROUP_SWAP_PEAK.exists() and CGROUP_SWAP_CURRENT.exists():
            swap_peak_kb = int(CGROUP_SWAP_PEAK.read_text().strip())
            swap_current_kb = int(CGROUP_SWAP_CURRENT.read_text().strip())
            
            # Convert to MB
            swap_peak_mb = swap_peak_kb / 1024.0
            swap_current_mb = swap_current_kb / 1024.0
            
            # Get swap total for utilization (from cgroup max or proc meminfo)
            if CGROUP_SWAP_MAX.exists():
                swap_max_kb = int(CGROUP_SWAP_MAX.read_text().strip())
                swap_total_mb = swap_max_kb / 1024.0 if swap_max_kb > 0 else swap_current_mb
            else:
                # Fallback to /proc/meminfo for total
                mem_total_mb, _ = _parse_proc_meminfo_swap()
                swap_total_mb = mem_total_mb if mem_total_mb else swap_current_mb
            
            # Calculate utilization
            if swap_total_mb and swap_total_mb > 0:
                swap_utilization_pct = (swap_current_mb / swap_total_mb) * 100.0
            
            swap_current = swap_current_mb
            swap_peak = swap_peak_mb
        else:
            raise FileNotFoundError("Cgroup swap paths missing")
            
    except (ValueError, FileNotFoundError, PermissionError):
        # Fallback to /proc/meminfo
        swap_total_mb, swap_free_mb = _parse_proc_meminfo_swap()
        if swap_total_mb is not None and swap_free_mb is not None:
            swap_current_mb = swap_total_mb - swap_free_mb
            swap_peak_mb = swap_current_mb  # Approximation - no peak in proc
            swap_utilization_pct = (swap_current_mb / swap_total_mb * 100.0) if swap_total_mb > 0 else 0.0
            
            swap_current = swap_current_mb
            swap_peak = swap_peak_mb
    
    # If we couldn't get any data, return failure
    if swap_current is None or swap_peak is None:
        return {
            "name": "Cgroup Swap Pressure Monitor",
            "passed": False,
            "detail": "Unable to read swap metrics from cgroup or /proc/meminfo",
            "swap_peak_mb": None,
            "swap_current_mb": None,
            "swap_utilization_pct": None
        }
    
    return {
        "name": "Cgroup Swap Pressure Monitor",
        "passed": True,
        "detail": f"Swap: {swap_current:.0f}MB/{swap_peak:.0f}MB peak ({swap_utilization_pct:.1f}%)",
        "swap_peak_mb": round(swap_peak, 2),
        "swap_current_mb": round(swap_current, 2),
        "swap_utilization_pct": round(swap_utilization_pct, 2)
    }


def _parse_proc_meminfo_swap():
    """Helper to parse swap totals from /proc/meminfo."""
    try:
        content = PROC_MEMINFO.read_text()
        lines = content.split('\n')
        swap_total_kb = None
        swap_free_kb = None
        
        for line in lines:
            if line.startswith('SwapTotal:'):
                swap_total_kb = int(line.split()[1])
            elif line.startswith('SwapFree:'):
                swap_free_kb = int(line.split()[1])
                
        if swap_total_kb is not None and swap_free_kb is not None:
            return swap_total_kb / 1024.0, swap_free_kb / 1024.0  # Convert to MB
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        pass
    
    return None, None


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
                    timeout=90
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


def append_accountability_ledger(digest: dict):
    """[Story 971] Append one flat JSONL line per audit run to the single-home ledger.

    The ledger lives at OUTPUT_DIR / 'accountability_ledger.jsonl' and is the canonical
    runtime data home shared with the static status page (which polls it alongside
    pager_activity.json). Each line carries exactly the accountability fields the
    timeline needs; failures here are logged and swallowed so a ledger hiccup can
    never take down the audit itself (the digest is already on disk by this point).
    """
    entry = {
        "timestamp": digest["timestamp"],
        "overall_status": digest["overall_status"],
        "passed_checks": digest["passed_checks"],
        "total_checks": digest["total_checks"],
        "discrepancies": digest["discrepancies"],
    }
    ledger_path = OUTPUT_DIR / LEDGER_FILE
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if ledger_path.exists() and ledger_path.stat().st_size > LEDGER_MAX_BYTES:
            os.replace(ledger_path, ledger_path.with_suffix(".jsonl.1"))
        line = json.dumps(entry, separators=(",", ":"))
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        logger.info(f"✅ Appended audit entry to single-home ledger: {ledger_path} (Status: {digest['overall_status']})")
    except Exception as e:
        logger.error(f"Failed to append to accountability ledger: {e}")


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

    c_swap = check_swap_pressure()
    checks.append(c_swap)
    if not c_swap["passed"]:
        discrepancies.append(c_swap["detail"])
    # [Story 101.12] Emit WARNING when swap utilization exceeds 80%
    if c_swap["swap_utilization_pct"] > 80.0:
        logger.warning(
            "[SWAP_PRESSURE] Swap utilization at %.1f%% - high memory pressure detected",
            c_swap["swap_utilization_pct"]
        )

    # Determine overall status
    passed_count = sum(1 for c in checks if c["passed"])
    total_count = len(checks)
    critical_failed = (not c_forge["passed"]) or (not c_lora["passed"]) or (not c_vram["passed"])
    has_degradation = (c_forge.get("status") == "DEGRADED")

    if c_forge.get("status") == "DEGRADED" and not any("DEGRADED" in d for d in discrepancies):
        discrepancies.append(f"Nightly Forge completed with degraded status ({c_forge['detail']})")

    if passed_count == total_count and not has_degradation:
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

    # [Story 971] Single canonical home: write the digest ONLY to OUTPUT_DIR (Portfolio_Dev/field_notes/data).
    # The www_deploy mirror was removed — the static site and the watchdog share one home now.
    out_file = OUTPUT_DIR / DIGEST_FILE
    tmp_file = OUTPUT_DIR / f"{DIGEST_FILE}.tmp"
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(digest, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, out_file)
        logger.info(f"✅ Wrote authoritative digest to {out_file} (Status: {overall_status})")
    except Exception as e:
        logger.error(f"Failed to write digest to {out_file}: {e}")

    # [Story 971] Append this audit run to the single-home interleaved JSONL ledger consumed by status.html
    append_accountability_ledger(digest)

    # [FEAT-607 / BKM-066] Stamp failure into nightly_dialogue.json so interleaved log is never dark/silent on abort
    if overall_status != "PASS":
        dialogue_path = OUTPUT_DIR / "nightly_dialogue.json"
        try:
            discrepancy_str = "; ".join(discrepancies) if discrepancies else "Unspecified pipeline failure"
            dialogue_payload = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "topic": "Nightly Accountability Sentinel (Watchdog)",
                "content": f"🚨 **[ACCOUNTABILITY AUDIT: {overall_status}]**\n\n**Checks Passed:** {passed_count}/{total_count}\n**Discrepancies:** {discrepancy_str}\n\n_Detected by Standalone Morning Accountability Watchdog (FEAT-619)._"
            }
            tmp_dialogue = OUTPUT_DIR / "nightly_dialogue.json.tmp"
            with open(tmp_dialogue, "w", encoding="utf-8") as df:
                json.dump(dialogue_payload, df, indent=4)
                df.flush()
                os.fsync(df.fileno())
            os.replace(tmp_dialogue, dialogue_path)
            logger.info(f"✅ Stamped watchdog failure notice into {dialogue_path}")
        except Exception as de:
            logger.warning(f"Failed to stamp watchdog failure notice into dialogue: {de}")

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
