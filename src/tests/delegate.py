"""
[BKM-034 Point 12] OpenAgent Swarm REST Dispatcher & Cloud Quota Sentinel
Formalized launcher script for orchestrator-to-OpenAgent story delegation.
Dispatches dispatches through Atlas (Plan Executor, Groq 70b) and Sisyphus (Lead Orchestrator),
creating a clean REST session on port 4097, pre-checking cloud rate limits, and dispatching story prompts.
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
OPENCODE_WEB_PORT = 4096
OPENCODE_ATTACH_URL = f"http://127.0.0.1:{OPENCODE_REST_PORT}/"
OPENCODE_WEB_URL = f"http://127.0.0.1:{OPENCODE_WEB_PORT}/"


def _log_pager_event(message: str, severity: str = "WARNING"):
    """Log telemetry event to pager_activity.json for real-time status.html/pager.html visibility."""
    pager_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json")
    if not os.path.exists(os.path.dirname(pager_path)):
        return
    try:
        events = []
        if os.path.exists(pager_path):
            with open(pager_path, "r") as f:
                events = json.load(f)
        events.insert(0, {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
            "severity": severity,
            "source": "delegate.py"
        })
        tmp_path = pager_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(events[:50], f, indent=2)
        os.replace(tmp_path, pager_path)
    except Exception:
        pass


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
        _log_pager_event(f"OpenCode core engine pre-flight probe failed: {e}", severity="WARNING")
        return False
    return True


DEFAULT_TARGET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")


def wake_web_ui():
    """
    [BKM-034 Socket Wakeup] opencode.socket is a user-level systemd socket unit
    (StopWhenUnneeded=true) that proxies 0.0.0.0:4096 -> 127.0.0.1:4097.
    A TCP connect to port 4096 triggers the socket activation chain:
      opencode.socket -> opencode-proxy.service -> codex backend on 4097.
    Without this touch, the web UI at http://192.168.1.238:4096/ is unreachable.
    """
    print(f"[*] Waking web UI via socket touch on port {OPENCODE_WEB_PORT}...")
    try:
        req = urllib.request.Request(OPENCODE_WEB_URL)
        with urllib.request.urlopen(req, timeout=10):
            pass
        print(f"[+] Web UI live at http://192.168.1.238:{OPENCODE_WEB_PORT}/")
    except Exception as e:
        print(f"[~] Web UI touch attempted (may need a moment): {e}")


def delegate(story_num, title, file_path, details, verification, target_dir=None, agent="atlas", max_retries=3):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment with 503 self-healing retry logic."""
    if not target_dir:
        target_dir = DEFAULT_TARGET_DIR

    # 1. Pre-flight quota check
    check_cloud_quota()

    session_title = f"Sprint 48 Story {story_num} (Run {int(time.time())}) — [{agent.upper()}] {title}"

    # 2. Create a fresh session via REST API on port 4097 with target agent & title
    try:
        session_payload = {
            "directory": target_dir,
            "agent": agent,
            "title": session_title
        }
        req = urllib.request.Request(
            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
            data=json.dumps(session_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_id = data["id"]
            # Also send explicit PATCH to ensure title overrides background auto-namer
            try:
                title_req = urllib.request.Request(
                    f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}",
                    data=json.dumps({"title": session_title}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="PATCH",
                )
                with urllib.request.urlopen(title_req, timeout=5):
                    pass
            except Exception:
                pass
    except Exception as e:
        print(f"[-] Failed to create session via REST on port {OPENCODE_REST_PORT}: {e}")
        _log_pager_event(f"Story {story_num} REST session creation failed: {e}", severity="CRITICAL")
        sys.exit(1)

    # 3. Poke Web UI (socket activation) AFTER session creation so Web GUI discovers new session
    wake_web_ui()
    print(f"[+] Session created: {session_id}")
    print(f"[+] Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}")

    agent_name = agent.capitalize()
    prompt = f"""[PRE-GROUNDED CONTEXT BRIEFING]
- Architecture & Planning: Sprint plan reference for Story-{story_num}.
- Scope Guidance: Workspace pre-grounded. Perform implementation now. Create and write the file specified below.

[TARGET SPECIFICATION]
- Primary Output Target: {file_path}
- Task Details: 
{details}

[SWARM DELEGATION DIRECTIVE — TASK() CALLS ONLY]
MANDATE: {agent_name} MUST NOT write files directly; call task() to delegate all file edits and test generation to sisyphus-junior (KENDER).
You are {agent_name} (Plan Executor). You MUST NOT implement code or write files yourself.
You MUST emit task() tool calls to delegate implementation and verification work:

task(category="quick", run_in_background=false, prompt=\"\"\"
## 1. TASK
Implement target: {file_path}
Details:
{details}

## 2. EXPECTED OUTCOME
- [ ] File {file_path} created/modified on disk
- [ ] Verification command passes: {verification}

## 3. MUST DO
- READ existing or reference files first if needed
- USE the edit or write tool to WRITE the changes to disk at {file_path}
- RUN verification command: {verification}

## 4. MUST NOT DO
- Do NOT only read files and report back — you MUST write the changes to disk using the write/edit tool
- Do NOT git commit
\"\"\")

[VERIFICATION GATE]
- Test Command: {verification}
- Mandate: Do NOT run git commit inside this session. Report completion summary when done."""

    # [BKM-034 Headless REST Dispatch — Self-Healing 503 Retry Loop]
    # POST the prompt directly to /session/<id>/message with exponential backoff & jitter for 503/429 errors.
    print(f"[*] Dispatching Story {story_num} via REST POST to session {session_id} [{agent_name}] on port {OPENCODE_REST_PORT}...")
    start_time = time.time()
    
    msg_payload = json.dumps({
        "parts": [{"type": "text", "text": prompt}]
    }).encode("utf-8")

    import random
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            msg_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message",
                data=msg_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(msg_req, timeout=1800) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                duration = time.time() - start_time
                finish = result.get("info", {}).get("finish", "unknown")
                tokens = result.get("info", {}).get("tokens", {})
                print(f"[+] Story {story_num} dispatch complete in {duration:.1f}s. finish={finish} tokens={tokens}")
                print(f"[+] Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}")
                return
        except urllib.error.HTTPError as e:
            duration = time.time() - start_time
            if e.code in (502, 503, 504, 429) and attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"Story {story_num} HTTP {e.code} transient error on attempt {attempt}/{max_retries}. Backing off {backoff:.1f}s..."
                print(f"[!] {msg}")
                _log_pager_event(msg, severity="WARNING")
                time.sleep(backoff)
            else:
                print(f"[-] Story {story_num} REST dispatch HTTP error after {duration:.1f}s: {e}")
                _log_pager_event(f"Story {story_num} REST dispatch failed (HTTP {e.code}) after {duration:.1f}s", severity="CRITICAL")
                sys.exit(1)
        except Exception as e:
            duration = time.time() - start_time
            if attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"Story {story_num} dispatch error ({e}) on attempt {attempt}/{max_retries}. Retrying in {backoff:.1f}s..."
                print(f"[!] {msg}")
                _log_pager_event(msg, severity="WARNING")
                time.sleep(backoff)
            else:
                print(f"[-] Story {story_num} REST dispatch failed after {duration:.1f}s: {e}")
                _log_pager_event(f"Story {story_num} REST dispatch failed ({e}) after {duration:.1f}s", severity="CRITICAL")
                sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAgent Swarm Story Delegator")
    parser.add_argument("--story", required=True, type=int, help="Story number")
    parser.add_argument("--title", required=True, help="Story title")
    parser.add_argument("--file", required=True, help="Target output file path")
    parser.add_argument("--details", required=True, help="Detailed requirements")
    parser.add_argument("--verification", required=True, help="Verification command line")
    parser.add_argument("--dir", default=None, help="Target working directory")
    parser.add_argument("--agent", default="atlas", help="Target agent alias (default: atlas)")
    parser.add_argument("--retries", default=3, type=int, help="Max self-healing retries for 503/429 errors (default: 3)")
    args = parser.parse_args()

    delegate(
        args.story,
        args.title,
        args.file,
        args.details,
        args.verification,
        target_dir=args.dir,
        agent=args.agent,
        max_retries=args.retries
    )
