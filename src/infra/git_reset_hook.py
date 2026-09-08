#!/usr/bin/env python3
"""
[FEAT-537 / FEAT-149] Git-Anchored 10-Minute Rolling Reset & Escalation Engine

Executes on post-commit:
1. Evaluates committed files against the Risk Hierarchy.
2. If Attendant code modified -> Immediately restarts Attendant daemon.
3. If Deep or Resident files modified -> Updates pending_reset.json with monotonic escalation and resets 10-minute rolling timer.
4. If only passive docs/HTML modified -> Leaves existing pending action untouched (or NONE).
"""

import os
import sys
import json
import time
import subprocess
import logging

BASE_DIR = "/home/jallred/Dev_Lab"
PORTFOLIO_DIR = os.path.join(BASE_DIR, "Portfolio_Dev")
LAB_DIR = os.path.join(BASE_DIR, "HomeLabAI")
PENDING_RESET_PATH = os.path.join(PORTFOLIO_DIR, "field_notes/data/pending_reset.json")
STATUS_JSON_PATH = os.path.join(PORTFOLIO_DIR, "field_notes/data/status.json")

# Action Levels for Monotonic Escalation
LEVEL_NONE = 0
LEVEL_SOFT = 1
LEVEL_DEEP = 2

ACTION_NAMES = {
    LEVEL_NONE: "NONE",
    LEVEL_SOFT: "SOFT_RELOAD",
    LEVEL_DEEP: "DEEP_RESET"
}

ACTION_LEVELS = {
    "NONE": LEVEL_NONE,
    "SOFT_RELOAD": LEVEL_SOFT,
    "DEEP_RESET": LEVEL_DEEP
}

ROLLING_TIMER_SECONDS = 600 # 10 minutes

def get_committed_files(repo_path: str) -> list:
    """Gets list of files modified in the latest commit."""
    try:
        res = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        return files
    except Exception as e:
        # Fallback to git show
        try:
            res = subprocess.run(
                ["git", "show", "--pretty=", "--name-only", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return [f.strip() for f in res.stdout.splitlines() if f.strip()]
        except Exception:
            return []

def get_commit_hash(repo_path: str) -> str:
    """Gets 7-character short commit hash."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        return res.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def restart_attendant_immediately():
    """Immediately bounces the attendant supervisor if its code changed."""
    print("⚡ [Git Hook] Attendant code modified! Executing immediate Attendant restart...")
    try:
        subprocess.run(["pkill", "-f", "attendant_liveliness.py"], capture_output=True)
        py_bin = os.path.join(LAB_DIR, ".venv/bin/python3")
        att_script = os.path.join(LAB_DIR, "src/attendant_liveliness.py")
        log_out = open(os.path.join(BASE_DIR, "attendant.log"), "a")
        proc = subprocess.Popen([py_bin, att_script, "--supervise"], stdout=log_out, stderr=log_out, start_new_session=True)
        print(f"✅ [Git Hook] Lab Attendant restarted immediately (PID: {proc.pid})")
    except Exception as e:
        print(f"❌ [Git Hook] Failed to restart Attendant: {e}")

def evaluate_files(repo_name: str, files: list) -> tuple:
    """
    Evaluates modified files and returns (required_level, reasons, attendant_changed).
    Inverted Soft Logic: Any active code/config file triggers at least SOFT_RELOAD.
    DEEP_RESET: Foyer architecture, entrypoints, infrastructure, and configuration.
    """
    required_level = LEVEL_NONE
    reasons = []
    attendant_changed = False

    # Passive extensions and paths that NEVER trigger a reset
    PASSIVE_EXTS = (".md", ".txt", ".log", ".html", ".css", ".svg", ".png", ".jpg", ".jpeg", ".lock")
    PASSIVE_PATTERNS = ("docs/", "field_notes/data/", "field_notes/cache/", ".locks/", ".gitignore", "pytest.ini")

    for f in files:
        # Check if file is purely passive documentation, media, or data log
        if any(f.endswith(ext) for ext in PASSIVE_EXTS) or any(pat in f for pat in PASSIVE_PATTERNS):
            continue

        if repo_name == "HomeLabAI":
            if f in ["src/lab_attendant.py", "src/attendant_liveliness.py"]:
                attendant_changed = True
                reasons.append(f"{f} (Attendant Core)")

            # Deep Reset: Core architecture, networking, infra, and system config
            if (f.startswith("src/v5/foyer/") or 
                f == "src/acme_lab.py" or 
                f.startswith("src/infra/") or 
                f.startswith("config/")):
                required_level = max(required_level, LEVEL_DEEP)
                reasons.append(f"{f} (Deep Core/Infra Architecture)")
            else:
                # Inverted Logic: All other active code/modules require SOFT_RELOAD
                required_level = max(required_level, LEVEL_SOFT)
                reasons.append(f"{f} (Active Module)")

        elif repo_name == "Portfolio_Dev":
            # Portfolio_Dev active code changes
            if f.endswith((".py", ".sh", ".js")):
                required_level = max(required_level, LEVEL_SOFT)
                reasons.append(f"{f} (Portfolio Active Code)")

    return required_level, reasons, attendant_changed

def load_pending_reset() -> dict:
    """Loads existing pending_reset.json or returns default empty state."""
    if os.path.exists(PENDING_RESET_PATH):
        try:
            with open(PENDING_RESET_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "pending_action": "NONE",
        "action_level": LEVEL_NONE,
        "timer_expiry_ts": 0,
        "triggered_at_ts": 0,
        "last_commit": "none",
        "reasons": []
    }

def save_pending_reset(data: dict):
    """Atomically writes pending_reset.json."""
    os.makedirs(os.path.dirname(PENDING_RESET_PATH), exist_ok=True)
    temp_path = PENDING_RESET_PATH + ".tmp"
    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, PENDING_RESET_PATH)

def main():
    repo_path = os.getcwd()
    repo_name = os.path.basename(repo_path)
    commit_hash = get_commit_hash(repo_path)
    files = get_committed_files(repo_path)

    if not files:
        sys.exit(0)

    req_level, reasons, attendant_changed = evaluate_files(repo_name, files)

    if attendant_changed:
        restart_attendant_immediately()

    # Load existing state for monotonic escalation
    existing = load_pending_reset()
    existing_level = existing.get("action_level", ACTION_LEVELS.get(existing.get("pending_action", "NONE"), LEVEL_NONE))
    
    # Check if existing timer is still active
    now = time.time()
    existing_active = existing.get("timer_expiry_ts", 0) > now and existing_level > LEVEL_NONE

    if not existing_active:
        existing_level = LEVEL_NONE

    # Monotonic Escalation: Never lower level
    new_level = max(existing_level, req_level)

    if new_level > LEVEL_NONE:
        new_action = ACTION_NAMES[new_level]
        expiry_ts = int(now + ROLLING_TIMER_SECONDS)
        all_reasons = list(set(existing.get("reasons", []) + reasons))

        state_data = {
            "pending_action": new_action,
            "action_level": new_level,
            "timer_expiry_ts": expiry_ts,
            "triggered_at_ts": int(now),
            "last_commit": commit_hash,
            "repo": repo_name,
            "reasons": all_reasons
        }
        save_pending_reset(state_data)

        minutes_left = (expiry_ts - now) / 60.0
        escalation_note = " (ESCALATED)" if new_level > existing_level and existing_active else ""
        print(f"🔒 [Git Hook] Lab marked DIRTY: Pending {new_action}{escalation_note}")
        print(f"⏱️ [Git Hook] 10-Minute Rolling Timer reset: Auto-executes at {time.strftime('%H:%M:%S', time.localtime(expiry_ts))} ({minutes_left:.1f}m quiet window)")
        print(f"📋 [Git Hook] Reasons: {', '.join(reasons[:3]) if reasons else 'Commit updates'}")
    else:
        # Passive commit: If no active timer, maintain NONE
        if not existing_active:
            state_data = {
                "pending_action": "NONE",
                "action_level": LEVEL_NONE,
                "timer_expiry_ts": 0,
                "triggered_at_ts": int(now),
                "last_commit": commit_hash,
                "repo": repo_name,
                "reasons": []
            }
            save_pending_reset(state_data)
            print(f"⚡ [Git Hook] Passive commit ({commit_hash}) - No lab reset required.")
        else:
            # Top-up existing timer even on passive commit
            existing["timer_expiry_ts"] = int(now + ROLLING_TIMER_SECONDS)
            existing["last_commit"] = commit_hash
            save_pending_reset(existing)
            print(f"⏱️ [Git Hook] Timer topped up to 10m for active {existing['pending_action']} (Commit {commit_hash}).")

if __name__ == "__main__":
    main()
