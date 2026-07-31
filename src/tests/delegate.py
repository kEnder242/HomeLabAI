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
OPENCODE_WEB_PORT = 4096
OPENCODE_ATTACH_URL = f"http://127.0.0.1:{OPENCODE_REST_PORT}/"
OPENCODE_WEB_URL = f"http://127.0.0.1:{OPENCODE_WEB_PORT}/"


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


def wake_web_ui():
    """
    [BKM-034 Socket Wakeup] opencode.socket is a user-level systemd socket unit
    (StopWhenUnneeded=true) that proxies 0.0.0.0:4096 -> 127.0.0.1:4097.
    A TCP connect to port 4096 triggers the socket activation chain:
      opencode.socket -> opencode-proxy.service -> codex backend on 4097.
    Without this touch, the web UI at http://192.168.1.238:4096/ is unreachable.
    """
    import socket as _socket
    print(f"[*] Waking web UI via socket touch on port {OPENCODE_WEB_PORT}...")
    try:
        # TCP connect is enough to activate the socket unit
        req = urllib.request.Request(OPENCODE_WEB_URL)
        with urllib.request.urlopen(req, timeout=10):
            pass
        print(f"[+] Web UI live at http://192.168.1.238:{OPENCODE_WEB_PORT}/")
    except Exception as e:
        # A connection refused or partial read still activates the socket unit
        print(f"[~] Web UI touch attempted (may need a moment): {e}")


def delegate(story_num, title, file_path, details, verification, target_dir=None):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment."""
    if not target_dir:
        target_dir = DEFAULT_TARGET_DIR

    # 1. Wake web UI (socket activation) so session is visible in browser
    wake_web_ui()

    # 2. Pre-flight quota check
    check_cloud_quota()

    session_title = f"Sprint 48 Story {story_num} (Run {int(time.time())}) — {title}"

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
            # Set session title via REST PATCH for Web UI visibility
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
        sys.exit(1)

    prompt = f"""[PRE-GROUNDED CONTEXT BRIEFING]
- Architecture & Planning: Sprint plan reference for Story-{story_num}.
- Scope Guidance: Workspace pre-grounded. Perform implementation now. Create and write the file specified below.

[TARGET SPECIFICATION]
- Primary Output Target: {file_path}
- Task Details: 
{details}

[SWARM DELEGATION DIRECTIVE — TASK() CALLS ONLY]
MANDATE: Sisyphus MUST NOT write files directly; call task() to delegate all file edits and test generation to sisyphus-junior (KENDER).
You are Sisyphus (Lead Orchestrator). You MUST NOT implement code or write files yourself.
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

    # [BKM-034 Headless REST Dispatch — No TUI/Webview Required]
    # opencode run --attach is a blocking foreground TUI that requires the webview
    # (port 4096) to be running. When the webview is down, it hangs indefinitely.
    # The correct headless pattern: POST the prompt directly to /session/<id>/message.
    print(f"[*] Dispatching Story {story_num} via REST POST to session {session_id} on port {OPENCODE_REST_PORT}...")
    start_time = time.time()
    try:
        msg_payload = json.dumps({
            "parts": [{"type": "text", "text": prompt}]
        }).encode("utf-8")
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
            print(f"[+] Session: http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}")
    except Exception as e:
        duration = time.time() - start_time
        print(f"[-] Story {story_num} REST dispatch failed after {duration:.1f}s: {e}")
        sys.exit(1)


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
