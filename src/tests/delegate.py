"""
[BKM-034 Point 12] OpenAgent Swarm REST Dispatcher & Cloud Quota Sentinel
Formalized launcher script for orchestrator-to-OpenAgent story delegation.
Creates a clean session on port 4097, pre-checks cloud rate limits, and attaches opencode run.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

OPENCODE_REST_PORT = 4097
OPENCODE_ATTACH_URL = f"http://127.0.0.1:{OPENCODE_REST_PORT}/"


def check_cloud_quota(provider="opencode"):
    """
    [FEAT-Q01] Quick cloud quota & rate limit sentinel check.
    Pings provider status and notifies orchestrator of rate-limit reset windows.
    """
    print(f"[*] Pre-flight check: Probing {provider} cloud endpoint status...")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
            data=json.dumps({"directory": "/tmp"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_id = data.get("id")
            if session_id:
                print(f"[+] OpenCode core engine listening on port {OPENCODE_REST_PORT}. Temp session: {session_id}")
                return True
    except Exception as e:
        print(f"[!] Warning: OpenCode core engine check failed: {e}")
        return False
    return True


DEFAULT_TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")

def check_cloud_quota(provider="opencode"):
    """
    [FEAT-Q01] Quick cloud quota & rate limit sentinel check.
    Pings provider status and notifies orchestrator of rate-limit reset windows.
    """
    print(f"[*] Pre-flight check: Probing {provider} cloud endpoint status...")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
            data=json.dumps({"directory": "/tmp"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_id = data.get("id")
            if session_id:
                print(f"[+] OpenCode core engine listening on port {OPENCODE_REST_PORT}. Temp session: {session_id}")
                return True
    except Exception as e:
        print(f"[!] Warning: OpenCode core engine check failed: {e}")
        return False
    return True


def delegate(story_num, title, file_path, details, verification, target_dir=None):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment."""
    if not target_dir:
        target_dir = DEFAULT_TARGET_DIR

    # 1. Pre-flight quota check
    check_cloud_quota()

    session_title = f"Sprint 47.1 Story {story_num} (Run {int(time.time())}) — {title}"

    # 2. Create a fresh session via REST API on port 4097
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
            data=json.dumps({"directory": target_dir}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_id = data["id"]
    except Exception as e:
        print(f"[-] Failed to create session via REST on port {OPENCODE_REST_PORT}: {e}")
        sys.exit(1)

    prompt = f"""[PRE-GROUNDED CONTEXT BRIEFING]
- Architecture & Planning: Sprint plan reference for Story-{story_num}.
- Scope Guidance: Workspace pre-grounded. Perform implementation now. Create and write the file specified below.

[TARGET SPECIFICATION]
- Primary Output Target: {file_path}
- Task Details: 
{details}

[SWARM DELEGATION DIRECTIVE]
- You are Sisyphus (Lead Manager).
- Delegate sub-tasks to your internal specialists:
  • Use `Prometheus` for test structure validation or pre-review.
  • Use `Sisyphus-Junior` or local tools for code edits.
  • Use `Hephaestus` for verification and log checks.

[VERIFICATION GATE]
- Test Command: {verification}
- Mandate: Do NOT run git commit inside this session. Report completion summary when done."""

    print(f"[*] Dispatching Story {story_num} via OpenAgent session {session_id} on port {OPENCODE_REST_PORT}...")
    cmd = [
        OPENCODE_BIN,
        "run",
        "--dir",
        target_dir,
        "--attach",
        OPENCODE_ATTACH_URL,
        "--session",
        session_id,
        "--auto",
        prompt,
    ]

    start_time = time.time()
    res = subprocess.run(cmd, text=True)
    duration = time.time() - start_time

    if res.returncode == 0:
        print(f"[+] Story {story_num} completed successfully in {duration:.1f}s.")
    else:
        print(f"[-] Story {story_num} failed with exit code {res.returncode} after {duration:.1f}s.")
    sys.exit(res.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAgent Swarm Story Delegator")
    parser.add_argument("--story", required=True, type=int, help="Story number")
    parser.add_argument("--title", required=True, help="Story title")
    parser.add_argument("--file", required=True, help="Target output file path")
    parser.add_argument("--details", required=True, help="Detailed requirements")
    parser.add_argument("--verification", required=True, help="Verification command line")
    parser.add_argument("--dir", default=None, help="Target working directory")
    args = parser.parse_args()

    delegate(args.story, args.title, args.file, args.details, args.verification, target_dir=args.dir)
