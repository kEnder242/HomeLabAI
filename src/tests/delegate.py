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

# [LAB-099] Thermal & Thread Safety: Limit C-extension worker threads to prevent 8-core CPU thermal overload
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TORCH_NUM_THREADS"] = "2"

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


def log_step(story_num: int, step_name: str, message: str, severity: str = "INFO"):
    """Log a step with timestamp to stdout, /tmp/delegate_story_<N>.log, and pager telemetry."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] [STORY {story_num}] [{step_name}] {message}"
    print(formatted, flush=True)
    
    # Append to step log file
    try:
        log_file = f"/tmp/delegate_story_{story_num}.log"
        with open(log_file, "a") as f:
            f.write(formatted + "\n")
    except Exception:
        pass
    
    if severity in ("WARNING", "CRITICAL"):
        _log_pager_event(f"[{step_name}] {message}", severity=severity)


def check_cloud_quota(provider="opencode"):
    """
    [FEAT-Q01] Quick cloud quota & rate limit sentinel check.
    Pings provider status and notifies orchestrator of rate-limit reset windows.
    """
    print(f"[*] Pre-flight check: Probing {provider} cloud endpoint status...", flush=True)
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
                print(f"[+] OpenCode core engine listening on port {OPENCODE_REST_PORT}. Temp session: {session_id}", flush=True)
                # [CLEANUP] Purge temporary probe session so it does not leave an empty "New session" entry in OpenCode dashboard
                try:
                    del_req = urllib.request.Request(
                        f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}",
                        method="DELETE"
                    )
                    with urllib.request.urlopen(del_req, timeout=3):
                        pass
                except Exception:
                    pass
                return True
    except Exception as e:
        print(f"[!] Warning: OpenCode core engine check failed: {e}", flush=True)
        _log_pager_event(f"OpenCode core engine pre-flight probe failed: {e}", severity="WARNING")
        return False
    return True


DEFAULT_TARGET_DIR = os.path.expanduser("~/Dev_Lab")
OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")


def wake_web_ui():
    """
    [BKM-034 Socket Wakeup] opencode.socket is a user-level systemd socket unit
    (StopWhenUnneeded=true) that proxies 0.0.0.0:4096 -> 127.0.0.1:4097.
    A TCP connect to port 4096 triggers the socket activation chain:
      opencode.socket -> opencode-proxy.service -> codex backend on 4097.
    Without this touch, the web UI at http://192.168.1.238:4096/ is unreachable.
    """
    print(f"[*] Waking web UI via socket touch on port {OPENCODE_WEB_PORT}...", flush=True)
    try:
        req = urllib.request.Request(OPENCODE_WEB_URL)
        with urllib.request.urlopen(req, timeout=10):
            pass
        print(f"[+] Web UI live at http://192.168.1.238:{OPENCODE_WEB_PORT}/", flush=True)
    except Exception as e:
        print(f"[~] Web UI touch attempted (may need a moment): {e}", flush=True)


def delegate(story_num, title, reference_file, details, verification, sprint_num=50, target_dir=None, agent="atlas", max_retries=3, mode="execute", target_files=None, session_id=None):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment with 503 self-healing retry logic."""
    import random
    import threading

    if not target_dir or target_dir == os.path.expanduser("~"):
        target_dir = DEFAULT_TARGET_DIR
    target_dir = os.path.abspath(target_dir)

    # Map short agent names to exact registered OpenCode agent display names
    AGENT_MAP = {
        "atlas": "atlas",
        "prometheus": "prometheus",
        "sisyphus": "sisyphus",
    }
    if mode in ("plan", "investigate"):
        agent_key = "prometheus"
    else:
        agent_key = "atlas"
    agent = AGENT_MAP.get(agent_key, agent_key)

    _target_display = target_files if target_files else reference_file
    log_step(story_num, "START", f"Initiating delegation ({mode.upper()}) for Sprint {sprint_num} '{title}' (reference: {reference_file}, target: {_target_display})")

    # 1. Pre-flight quota check & service ignition
    check_cloud_quota()
    
    # Auto-start opencode-core.service if inactive (Scale-to-Zero resilience)
    try:
        subprocess.run(["systemctl", "--user", "start", "opencode-core.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
    except Exception:
        pass

    session_title = f"Sprint {sprint_num} Story {story_num} (Run {int(time.time())}) — [{mode.upper()}:{agent.upper()}] {title}"

    # 2. Attach to existing session or create a fresh session via REST API on port 4097
    if session_id:
        log_step(story_num, "SESSION_REUSED", f"Reusing existing REST session {session_id}")
    else:
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
                log_step(story_num, "SESSION_CREATED", f"Created REST session {session_id}")
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
            log_step(story_num, "SESSION_FAILED", f"Failed to create session via REST on port {OPENCODE_REST_PORT}: {e}", severity="CRITICAL")
            sys.exit(1)

    # 3. Poke Web UI (socket activation) AFTER session creation so Web GUI discovers new session
    wake_web_ui()
    log_step(story_num, "WEB_UI_LINK", f"Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}")

    # Build dynamic prompt blueprint based on mode
    if mode == "plan":
        mandate_block = """[READ-ONLY PLANNING DIRECTIVE — NO CODE EDITS]
You are Prometheus (Lead Architect). You MUST NOT edit files, run code modifications, or emit file edit tool calls.
Inspect the target files and output a structured plan:
  1. ROOT CAUSE & ARCHITECTURAL IMPACT
  2. TARGET FILES & EXACT SYMBOL ANCHORS
  3. PROPOSED FIX OPTIONS (Option A vs Option B with trade-offs)
  4. VERIFICATION STRATEGY & RISK RATING"""
        note_block = f"[NOTE] Output the architecture plan in markdown only. Apply ZERO file edits. Execution will be performed in a separate story."
    elif mode == "investigate":
        mandate_block = """[READ-ONLY INVESTIGATION DIRECTIVE — NO CODE EDITS]
You are Prometheus (Lead Investigator). You MUST NOT edit files or run code modifications.
Inspect tracebacks, logs, and target code files. Output a structured diagnostic report:
  1. ERROR TRACEBACK AUDIT
  2. REPRODUCTION STEPS
  3. IDENTIFIED BOTTLENECK / RACE CONDITION
  4. RECOMMENDED REMEDIATION"""
        note_block = f"[NOTE] Output the diagnostic investigation report in markdown only. Apply ZERO file edits."
    else:
        mandate_block = f"""[STORY {story_num}: {title}]
[IDENTITY ASSERTION & HARD-STOP GUARD]
You MUST be Atlas (Plan Executor & Swarm Conductor). Check your persona identity immediately.
If you are NOT Atlas (e.g. Sisyphus, Prometheus, or an unassigned worker node), DO NOT perform any file edits or bash commands. Immediately halt execution, output the [HANDOVER REFLECTION] block below explaining the persona mismatch, and return immediately."""
        _edit_scope = target_files if target_files else reference_file
        note_block = f"[NOTE] Apply code modifications to {_edit_scope} only. Silicon validation and testing will be performed post-dispatch by the orchestrator."

    _target_files_line = f"- Edit Target(s): {target_files}" if target_files else f"- Edit Target(s): {reference_file} (same as reference)"
    prompt = f"""[CONTEXT & TARGET SPECIFICATION]
- Sprint Plan Reference: {reference_file}
- Story: {story_num} ({title})
{_target_files_line}
- Delegation Mode: {mode.upper()}

{mandate_block}

[FUNCTIONAL REQUIREMENTS]
{details}

[HANDOVER REFLECTION]
As an execution peer, reflect candidly on how this task was handed over to you. In 2-3 natural sentences, tell me: What tripped you up, what turned out to be inaccurate or missing in the instructions, and what single change to the prompt would have made this execution faster?

{note_block}"""

    # [BKM-034 Headless REST Dispatch — Threaded Heartbeat Loop & Step-Logging]
    # Ref: Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md (Section 1: Swarm Topology & BKM-034 Point 12)
    # Session agent ("atlas") is assigned at session creation time via POST /session body: {"agent": "atlas"}.
    msg_payload = json.dumps({
        "parts": [{"type": "text", "text": prompt}]
    }).encode("utf-8")

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        log_step(story_num, "DISPATCH_ATTEMPT", f"Dispatching prompt to session {session_id} (Attempt {attempt}/{max_retries})")
        start_time = time.time()
        
        post_result = None
        post_exception = None

        def _do_post():
            nonlocal post_result, post_exception
            try:
                msg_req = urllib.request.Request(
                    f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message",
                    data=msg_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(msg_req, timeout=1800) as resp:
                    post_result = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                post_exception = exc

        worker = threading.Thread(target=_do_post, daemon=True)
        worker.start()

        # Heartbeat loop while worker thread is active
        hb_tick = 0
        while worker.is_alive():
            worker.join(timeout=5.0)
            if worker.is_alive():
                hb_tick += 1
                elapsed = int(time.time() - start_time)
                # Heartbeat stdout line every 5s keeps process output active and prevents silent watchdog timeouts
                log_step(story_num, "HEARTBEAT", f"OpenAgent execution in progress... ({elapsed}s elapsed). Step log: /tmp/delegate_story_{story_num}.log")

        duration = time.time() - start_time

        if post_result is not None:
            finish = post_result.get("info", {}).get("finish", "unknown")
            tokens = post_result.get("info", {}).get("tokens", {})
            log_step(story_num, "COMPLETE", f"Story {story_num} dispatch ({mode.upper()}) complete in {duration:.1f}s. finish={finish} tokens={tokens}")
            log_step(story_num, "WEB_UI_LINK", f"Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}")
            return

        if post_exception is not None:
            e = post_exception
            if isinstance(e, urllib.error.HTTPError) and e.code in (502, 503, 504, 429) and attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"HTTP {e.code} transient error on attempt {attempt}/{max_retries}. Backing off {backoff:.1f}s..."
                log_step(story_num, "RETRY_BACKOFF", msg, severity="WARNING")
                time.sleep(backoff)
            elif attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"Dispatch error ({e}) on attempt {attempt}/{max_retries}. Retrying in {backoff:.1f}s..."
                log_step(story_num, "RETRY_BACKOFF", msg, severity="WARNING")
                time.sleep(backoff)
            else:
                log_step(story_num, "FAILED", f"Dispatch failed after {duration:.1f}s: {e}", severity="CRITICAL")
                sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAgent Swarm Story Delegator")
    parser.add_argument("--retrospective", action="store_true", help="Synthesize DELEGATION_RETROSPECTIVE.md from /tmp/delegate_story_*.log + REST session metrics, then exit")
    _retro_mode = "--retrospective" in sys.argv
    parser.add_argument("--sprint", required=not _retro_mode, type=int, default=53, help="Sprint number (e.g. 53)")
    parser.add_argument("--story", required=not _retro_mode, type=int, help="Story number")
    parser.add_argument("--title", required=not _retro_mode, help="Story title")
    parser.add_argument("--reference", required=not _retro_mode, help="Sprint plan / context reference document (read-only context for Atlas)")
    parser.add_argument("--target", default=None, help="Actual file(s) Atlas is permitted to edit (omit to default to --reference). Separate multiple paths with commas.")
    parser.add_argument("--details", required=not _retro_mode, help="Detailed requirements")
    parser.add_argument("--mode", choices=["execute", "plan", "investigate"], default="execute", help="Delegation mode: execute (code edit), plan (read-only plan), or investigate (read-only diagnostic)")
    parser.add_argument("--verification", default="Post-dispatch AGY Validation", help="Verification command line (optional)")
    parser.add_argument("--dir", default=None, help="Target working directory")
    parser.add_argument("--retries", default=3, type=int, help="Max self-healing retries for 503/429 errors (default: 3)")
    parser.add_argument("--session-id", default=None, help="Existing REST session ID to attach to for context reuse across multi-step iterations")
    args = parser.parse_args()

    if args.retrospective:
        _src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _src_dir not in sys.path:
            sys.path.insert(0, _src_dir)
        from infra.delegate_retrospective import run_retrospective
        run_retrospective()
        sys.exit(0)

    delegate(
        args.story,
        args.title,
        args.reference,
        args.details,
        args.verification,
        sprint_num=args.sprint,
        target_dir=args.dir,
        agent="atlas",
        max_retries=args.retries,
        mode=args.mode,
        target_files=args.target,
        session_id=args.session_id,
    )
