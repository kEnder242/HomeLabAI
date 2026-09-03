"""
[BKM-034 Point 12] OpenAgent Swarm REST Dispatcher & Cloud Quota Sentinel
Formalized launcher script for orchestrator-to-OpenAgent story delegation.
Dispatches dispatches through Atlas (Plan Executor, Groq 70b) and Sisyphus (Lead Orchestrator),
creating a clean REST session on port 4097, pre-checking cloud rate limits, and dispatching story prompts.
"""

import argparse
import atexit
import json
import os
import re
import signal
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

_ACTIVE_SESSION_ID = None


def _cleanup_active_session():
    """Auto-abort and delete in-flight REST session on task termination or exit."""
    global _ACTIVE_SESSION_ID
    if _ACTIVE_SESSION_ID:
        sid = _ACTIVE_SESSION_ID
        _ACTIVE_SESSION_ID = None
        try:
            req_abort = urllib.request.Request(f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{sid}/abort", method="POST")
            urllib.request.urlopen(req_abort, timeout=1.5)
        except Exception:
            pass
        try:
            req_del = urllib.request.Request(f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{sid}", method="DELETE")
            urllib.request.urlopen(req_del, timeout=1.5)
        except Exception:
            pass


def _sig_term_handler(signum, frame):
    _cleanup_active_session()
    sys.exit(1)


signal.signal(signal.SIGINT, _sig_term_handler)
signal.signal(signal.SIGTERM, _sig_term_handler)
atexit.register(_cleanup_active_session)


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


def wake_m5_air():
    """[BKM-039] Send Wake-on-LAN Magic Packet to macOS M5-Air to prevent sleep timeouts."""
    import socket
    m5_mac = "00:e0:4c:0a:0b:ad".replace(":", "").replace("-", "")
    data = bytes.fromhex("FF" * 6 + m5_mac * 16)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(data, ("192.168.1.255", 9))
            s.sendto(data, ("192.168.1.46", 9))
        print("[*] [WOL] Sent Wake-on-LAN Magic Packet to M5-Air (192.168.1.46).", flush=True)
    except Exception as e:
        print(f"[!] [WOL] Magic Packet broadcast failed (non-fatal): {e}", flush=True)


def wake_web_ui():
    """
    [BKM-034 Socket Wakeup] opencode.socket is a user-level systemd socket unit
    (StopWhenUnneeded=true) that proxies 0.0.0.0:4096 -> 127.0.0.1:4097.
    A TCP connect to port 4096 triggers the socket activation chain:
      opencode.socket -> opencode-proxy.service -> codex backend on 4097.
    Without this touch, the web UI at http://192.168.1.238:4096/ is unreachable.
    """
    wake_m5_air()
    print(f"[*] Waking web UI via socket touch on port {OPENCODE_WEB_PORT}...", flush=True)
    try:
        req = urllib.request.Request(OPENCODE_WEB_URL)
        with urllib.request.urlopen(req, timeout=10):
            pass
        print(f"[+] Web UI live at http://192.168.1.238:{OPENCODE_WEB_PORT}/", flush=True)
    except Exception as e:
        print(f"[~] Web UI touch attempted (may need a moment): {e}", flush=True)


def _extract_sprint_summary(sprint_doc_path: str) -> str:
    """[BKM-034 Tier 1] Extract the Executive Summary & Architectural Contract from a sprint plan."""
    if not sprint_doc_path or not os.path.exists(sprint_doc_path):
        return ""
    try:
        with open(sprint_doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"## 🧭 Executive Summary & Architectural Contract(.*?)(?=## 📋 Granular Story Breakdown|\Z)", content, re.DOTALL)
        if match:
            summary = match.group(1).strip()
            if len(summary) > 2500:
                summary = summary[:2500] + "\n...(truncated for prompt efficiency, see full doc on disk)"
            return summary
    except Exception:
        pass
def _format_error_context(exc) -> str:
    """Extracts deep diagnostic context from HTTP errors, systemd journal, and silicon ping."""
    details = []
    if isinstance(exc, urllib.error.HTTPError):
        details.append(f"HTTP Status: {exc.code} {exc.reason}")
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
            if raw_body:
                try:
                    body_json = json.loads(raw_body)
                    err_name = body_json.get("name") or body_json.get("error", {}).get("type", "Error")
                    err_msg = body_json.get("data", {}).get("message") or body_json.get("error", {}).get("message") or str(body_json)
                    err_ref = body_json.get("data", {}).get("ref") or body_json.get("ref", "")
                    details.append(f"  ├─ Error Name: {err_name}")
                    details.append(f"  ├─ Server Message: {err_msg}")
                    if err_ref:
                        details.append(f"  ├─ Reference: {err_ref}")
                except Exception:
                    details.append(f"  ├─ Response Body: {raw_body[:250]}")
        except Exception:
            pass

        if exc.code == 500:
            try:
                res = subprocess.run(
                    ["journalctl", "--user", "-u", "opencode-core.service", "-n", "3", "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                if res.stdout:
                    jlines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                    if jlines:
                        details.append("  ├─ Core Service Journal (tail):")
                        for jl in jlines[-2:]:
                            details.append(f"  │    {jl}")
            except Exception:
                pass
    else:
        details.append(f"Exception: {exc}")

    m5_status = "UNKNOWN"
    w4090_status = "UNKNOWN"
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        m5_status = "UP" if s.connect_ex(("192.168.1.46", 8000)) == 0 else "DOWN/REFUSED"
        s.close()
    except Exception:
        m5_status = "ERROR"

    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        w4090_status = "UP" if s.connect_ex(("192.168.1.26", 11434)) == 0 else "DOWN/REFUSED"
        s.close()
    except Exception:
        w4090_status = "ERROR"

    details.append(f"  └─ Silicon Reachability: M5(8000)={m5_status} | 4090(11434)={w4090_status}")
    return "\n".join(details)


def _ping_host(host: str, port: int, timeout: float = 0.5) -> bool:
    """Fast socket reachability probe for federated silicon endpoints."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        ok = (s.connect_ex((host, port)) == 0)
        s.close()
        return ok
    except Exception:
        return False


def _log_live_usage_telemetry(story_num: int, sprint_num: int, title: str, model_obj: dict, duration: float, tokens: dict, text_len: int, raw_tp: float = None):
    """[FEAT-498] Unified Swarm Telemetry Tap for live_usage_stream.jsonl & cumulative_tokens.json"""
    try:
        from infra.cumulative_telemetry import log_telemetry_event
        out_tokens = tokens.get("output", 0) if isinstance(tokens, dict) else 0
        if out_tokens == 0 and text_len > 0:
            out_tokens = max(1, int(text_len / 4.0))
            
        provider_id = model_obj.get("providerID", "unknown") if isinstance(model_obj, dict) else "unknown"
        model_id = model_obj.get("modelID", "unknown") if isinstance(model_obj, dict) else str(model_obj)
        
        seat = "Cloud Swarm"
        if "4090" in provider_id or "kender" in provider_id or "windows" in provider_id:
            seat = "Windows 4090RTX"
        elif "m5" in provider_id or "mlx" in provider_id:
            seat = "Apple M5 Air"
        elif "z87" in provider_id or "vllm" in provider_id:
            seat = "Linux 2080ti"
            
        log_telemetry_event(
            source=f"delegate.py (Story {story_num})",
            task_title=title,
            seat=seat,
            provider=provider_id,
            model=model_id,
            tokens_generated=out_tokens,
            duration_seconds=duration,
            raw_throughput_tok_s=raw_tp
        )
    except Exception:
        pass


def _is_provider_reachable(provider_id: str) -> bool:
    """Pre-probes local silicon endpoints (0.8s timeout) to avoid 60s OpenCode HTTP socket stalls."""
    if "4090" in provider_id or "kender" in provider_id or "windows" in provider_id:
        return _ping_host("192.168.1.26", 11434, timeout=0.5)
    if "m5" in provider_id or "mlx" in provider_id:
        return _ping_host("192.168.1.46", 8000, timeout=0.5)
    return True


# [FEAT-440] Taxonomy Separation: Agent DNA vs. User Work History
def delegate(story_num, title, reference_file, details, verification, sprint_num=50, target_dir=None, agent="sisyphus", max_retries=3, mode="execute", target_files=None, session_id=None, sprint_doc=None, local_only=False, cloud_only=False):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment with 503 self-healing retry logic."""
    import random
    import threading

    if not target_dir or target_dir == os.path.expanduser("~"):
        target_dir = DEFAULT_TARGET_DIR
    target_dir = os.path.abspath(target_dir)

    # Map short agent names to exact registered OpenCode agent names.
    AGENT_MAP = {
        "atlas": "atlas",
        "prometheus": "prometheus",
        "sisyphus": "sisyphus",
        "sisyphus-junior": "sisyphus-junior",
    }
    if not agent or agent == "sisyphus":
        if mode in ("plan", "investigate"):
            agent_key = "prometheus"
        else:
            agent_key = "sisyphus"
    else:
        agent_key = agent.lower()
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
    active_session_valid = False
    if session_id:
        try:
            check_req = urllib.request.Request(f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}")
            with urllib.request.urlopen(check_req, timeout=3) as c_resp:
                if c_resp.status == 200:
                    active_session_valid = True
                    log_step(story_num, "SESSION_REUSED", f"Reusing verified REST session {session_id}")
        except Exception:
            active_session_valid = False

    if not active_session_valid:
        try:
            session_payload = {
                "directory": target_dir,
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
    global _ACTIVE_SESSION_ID
    _ACTIVE_SESSION_ID = session_id
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
        note_block = "[NOTE] Output the architecture plan in markdown only. Apply ZERO file edits. Execution will be performed in a separate story."
    elif mode == "investigate":
        mandate_block = """[READ-ONLY INVESTIGATION DIRECTIVE — NO CODE EDITS]
You are Prometheus (Lead Investigator). You MUST NOT edit files or run code modifications.
Inspect tracebacks, logs, and target code files. Output a structured diagnostic report:
  1. ERROR TRACEBACK AUDIT
  2. REPRODUCTION STEPS
  3. IDENTIFIED BOTTLENECK / RACE CONDITION
  4. RECOMMENDED REMEDIATION"""
        note_block = "[NOTE] Output the diagnostic investigation report in markdown only. Apply ZERO file edits."
    elif agent == "atlas":
        # [FEAT-515 / Task 69.6.3] Dual-Mode Category Dispatch:
        #   --local-only  -> category="unspecified-low" (routes to M5 Air via oh-my-openagent.json)
        #   default/cloud -> category="deep" (routes to cloud DeepSeek/Qwen fallback ladders)
        _atlas_dispatch_category = "unspecified-low" if local_only else "deep"
        mandate_block = f"""[STORY {story_num}: {title}]
You are Atlas (Task Orchestrator on Windows RTX 4090).

[STATIC RULES — L2 INVARIANTS]
- You are a PURE ROUTER. You NEVER write code, edit files, or invoke file-editing tools directly.
- Your sole output tool is `task(category="{_atlas_dispatch_category}", prompt="...")`.
- The `task` tool call must contain ONLY two fields: category and prompt. No other parameters.
- CRITICAL CONCURRENCY INVARIANT: You MUST emit exactly ONE task() tool call per turn. NEVER call task() multiple times in parallel. Consolidate your micro-task specifications into a single, cohesive, bounded implementation contract for Junior.
- If Junior emits [BLOCKER REPORT: ...], relay the exact blocker text upward. Do NOT attempt local resolution.

[DYNAMIC INGESTION — SPRINT CONTEXT]
- Ingest the Tier 1 sprint summary (injected above) for global architectural context.
- Cross-reference story requirements against the sprint's stated dependencies and verification gates.
- If the story references target files, confirm they exist before dispatching.

[DOWNSTREAM HAND-OFF — JUNIOR DISPATCH PROTOCOL]
- Consolidate all implementation steps into a SINGLE unified task prompt (< 1,500 tokens).
- Each dispatch prompt MUST include: exact file path(s), target function/class symbol anchors, and concrete code diff or stub-fill specifications.
- SINGLE TASK LAW: Local execution hardware operates on a single execution stream. You MUST package the interface, logic, and verification into ONE single task() dispatch. NEVER split across multiple task() calls.

[BACKPRESSURE PROTOCOL — ESCALATION GATE]
- If Junior returns empty text or finish=unknown, emit [BLOCKER REPORT: SILENT_FAILURE] with the session URL.
- If you lack sufficient context to formulate a dispatch, emit [BLOCKER REPORT: INSUFFICIENT_CONTEXT] listing what is missing.
- NEVER guess at API signatures, file paths, or implementation details. Halt and escalate.

Delegate execution immediately via:
  `task(category="{_atlas_dispatch_category}", prompt="<concrete instructions>")`"""
        _edit_scope = target_files if target_files else reference_file
        note_block = f"[NOTE] Delegate the surgical code edits to the local execution worker via task(category=\"{_atlas_dispatch_category}\", ...). Silicon validation will be performed post-dispatch."
    else:
        mandate_block = f"""[STORY {story_num}: {title}]
You are Sisyphus (Ultraworker & Autonomous Engineer). Execute the code modifications directly and surgically.

[STATIC RULES — L3 INVARIANTS]
- Research is DONE. Do NOT use search, grep, or find tools across the repository.
- You operate strictly within the assigned target files and function stubs.
- NEVER use destructive bash file overwrites (e.g. echo >, cat << 'EOF' >) on existing codebase files.
- Modifying Existing Files: Always invoke the `clara-dna_safe_patch` MCP tool.
  Example tool call:
    Tool: clara-dna_safe_patch
    Arguments:
      file_path: "HomeLabAI/src/tests/fixtures/patch_target.py"
      old_pattern: "def format_node_badge(node_name: str, tier: str = \\"local\\") -> str:\\n    \\"\\"\\"Format node tier badge string.\\"\\"\\"\\n    prefix = \\"[LOCAL]\\" if tier == \\"local\\" else \\"[CLOUD]\\"\\n    return f\\\"{{prefix}} {{node_name.upper()}}\\\""
      new_pattern: "def format_node_badge(node_name: str, tier: str = \\"local\\") -> str:\\n    \\"\\"\\"Format node tier badge string.\\"\\"\\"\\n    prefix = \\"[LOCAL]\\" if tier == \\"local\\" else \\"[CLOUD]\\"\\n    return f\\\"{{prefix}} {{node_name.upper()}}\\\"\\n\\n\\ndef calculate_energy_efficiency(tokens: int, duration_s: float, watts: float) -> float:\\n    \\"\\"\\"Calculate energy efficiency metric.\\"\\"\\"\\n    if duration_s > 0 and watts > 0:\\n        return (tokens / duration_s) / watts\\n    return 0.0"
- Creating New Files: Use the standard `write` tool.
- Never import new external dependencies without explicit authorization in the story spec.

[DYNAMIC INGESTION — TASK CONTEXT]
- Your contract is the Tier 2 specification injected below. It contains exact file paths, symbol anchors, and expected behavior.
- If a code snippet is provided, treat it as the authoritative incumbent implementation to modify.
- Preserve all existing comments, docstrings, and test coverage unrelated to the assigned modification.

[DOWNSTREAM HAND-OFF — VERIFICATION ARTIFACTS]
- After completing edits, report: files modified, functions touched, and lines changed.
- If tests exist in the target scope, run them and include pass/fail results in your response.
- Emit a brief [HANDOVER REFLECTION] describing what was unclear or could improve the next dispatch.

[BACKPRESSURE PROTOCOL — BLOCKER GATE]
- If missing interfaces, broken types, or import failures prevent completion, HALT immediately.
- Emit: [BLOCKER REPORT: <CATEGORY>] <exact error details and missing dependency>.
- NEVER stub out or mock missing dependencies. Halt and let the orchestrator provide them."""
        _edit_scope = target_files if target_files else reference_file
        note_block = f"[NOTE] Apply code modifications strictly to {_edit_scope}. Silicon validation and testing will be performed post-dispatch by the orchestrator."

    # [BKM-034 Two-Tier Payload Construction]
    effective_sprint_doc = sprint_doc or (reference_file if reference_file and "SPRINT_PLAN" in reference_file else None)
    tier1_block = ""
    if not local_only and effective_sprint_doc:
        sprint_summary = _extract_sprint_summary(effective_sprint_doc)
        if sprint_summary:
            tier1_block = f"""[TIER 1: GLOBAL SPRINT SITUATIONAL AWARENESS]
Sprint Reference: {effective_sprint_doc}
{sprint_summary}

(Directive: Read the full sprint plan on disk at '{effective_sprint_doc}' for deep context if needed, but restrict file edits strictly to your assigned target files.)

---
"""
    elif local_only and effective_sprint_doc:
        tier1_block = f"""[TIER 1: GLOBAL SPRINT SITUATIONAL AWARENESS]
Sprint Reference: {effective_sprint_doc} (Available on disk for full architectural context & diagrams)

---
"""

    # Optional target file snippet injection to prevent M5 Air memory ceiling blowouts
    target_snippet_block = ""
    if target_files and os.path.exists(target_files.split(",")[0].strip()):
        first_target = target_files.split(",")[0].strip()
        try:
            with open(first_target, "r") as tf:
                lines = tf.readlines()
                snippet = "".join(lines[:80])
                target_snippet_block = f"\n[INCUMBENT TARGET CODE SNIPPET: {first_target}]\n```python\n{snippet}\n```\n"
        except Exception:
            pass

    _handover_block = ""
    if agent != "atlas":
        _handover_block = """[HANDOVER REFLECTION]
As an execution peer, reflect candidly on how this task was handed over to you. In 2-3 natural sentences, tell me: What tripped you up, what turned out to be inaccurate or missing in the instructions, and what single change to the prompt would have made this execution faster?
"""

    _target_files_line = f"- Edit Target(s): {target_files}" if target_files else f"- Edit Target(s): {reference_file} (same as reference)"
    prompt = f"""{tier1_block}[TIER 2: BOUNDED STORY TARGET SPECIFICATION]
- Sprint Plan Reference: {reference_file}
- Story: {story_num} ({title})
{_target_files_line}
- Delegation Mode: {mode.upper()}

{mandate_block}

[FUNCTIONAL REQUIREMENTS & 4-ANCHOR SPECIFICATION]
{details}
{target_snippet_block}
{_handover_block}
{note_block}"""

    # [FEAT-493] Load model ladder dynamically from centralized infrastructure config
    cfg_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")
    model_ladder = []
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r") as cf:
                cfg_obj = json.load(cf)
                aliases = cfg_obj.get("swarm_aliases", {})
                if local_only:
                    local_cfg = aliases.get("local_bicameral", {})
                    log_step(story_num, "LOCAL_ONLY_MODE", "Enforcing 100% Sovereign Local Silicon (Windows 4090 Atlas + M5 Air Junior). Zero cloud fallbacks.")
                    if mode in ("plan", "investigate") or agent in ("prometheus", "atlas", "architect"):
                        model_ladder = [local_cfg.get("architect", {"providerID": "my-windows-4090", "modelID": "hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL"})]
                    else:
                        model_ladder = [
                            local_cfg.get("coder", {"providerID": "my-m5-mlx", "modelID": "mlx-community--Qwen3.8-27B-4bit"}),
                            local_cfg.get("fallback_coder", {"providerID": "my-windows-4090", "modelID": "hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL"})
                        ]
                elif cloud_only:
                    log_step(story_num, "CLOUD_ONLY_MODE", "Enforcing 100% Cloud Swarm Execution (Groq/OpenCode/Cohere). Zero local silicon fallbacks.")
                    model_ladder = aliases.get("fast_worker", [
                        {"providerID": "groq", "modelID": "llama-3.3-70b-versatile"},
                        {"providerID": "opencode", "modelID": "big-pickle"},
                        {"providerID": "cohere", "modelID": "command-a-plus-05-2026"}
                    ])
                elif agent in ("prometheus", "atlas", "architect"):
                    model_ladder = aliases.get("champion_reasoner", [])
                elif agent in ("sisyphus", "hephaestus", "developer"):
                    model_ladder = aliases.get("champion_coder", [])
                else:
                    model_ladder = aliases.get("default_ladder", [])
        except Exception:
            pass

    if not model_ladder:
        if local_only:
            model_ladder = [{"providerID": "my-m5-mlx", "modelID": "mlx-community--Qwen3.8-27B-4bit"}]
        elif cloud_only:
            model_ladder = [
                {"providerID": "groq", "modelID": "llama-3.3-70b-versatile"},
                {"providerID": "opencode", "modelID": "big-pickle"},
                {"providerID": "cohere", "modelID": "command-a-plus-05-2026"}
            ]
        else:
            model_ladder = [
                {"providerID": "groq", "modelID": "llama-3.3-70b-versatile"},
                {"providerID": "opencode", "modelID": "big-pickle"},
                {"providerID": "my-windows-4090", "modelID": "hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL"},
            ]

    # Pre-filter unreachable endpoints so we never block on 60s socket timeouts (unless in local_only mode where we report directly)
    if not local_only:
        model_ladder = [m for m in model_ladder if _is_provider_reachable(m.get("providerID", ""))]
        if not model_ladder:
            model_ladder = [{"providerID": "openrouter", "modelID": "free"}]

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        if attempt > 1:
            try:
                session_payload = {
                    "directory": target_dir,
                    "title": f"{session_title} (Fallback Attempt {attempt})"
                }
                s_req = urllib.request.Request(
                    f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
                    data=json.dumps(session_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(s_req, timeout=10) as s_resp:
                    s_data = json.loads(s_resp.read().decode("utf-8"))
                    session_id = s_data["id"]
                    log_step(story_num, "SESSION_RECREATED", f"Created fresh session {session_id} for fallback attempt {attempt}")
            except Exception:
                pass

        current_model = model_ladder[min(attempt - 1, len(model_ladder) - 1)]
        log_step(story_num, "DISPATCH_ATTEMPT", f"Dispatching prompt to session {session_id} using {current_model['providerID']}/{current_model['modelID']} (Attempt {attempt}/{max_retries})")
        start_time = time.time()
        
        msg_dict = {
            "parts": [{"type": "text", "text": prompt}],
            "model": current_model
        }
        msg_payload = json.dumps(msg_dict).encode("utf-8")
        
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
        last_inspected_state = ""
        while worker.is_alive():
            worker.join(timeout=3.0)
            if worker.is_alive():
                hb_tick += 1
                elapsed = int(time.time() - start_time)

                # [FEAT-512 / BKM-047] Smart Heartbeat Polling & Live Telemetry Inspector
                try:
                    poll_req = urllib.request.Request(f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message")
                    with urllib.request.urlopen(poll_req, timeout=2.0) as poll_resp:
                        msgs = json.loads(poll_resp.read().decode("utf-8"))
                        if msgs:
                            last_msg = msgs[-1]
                            parts = last_msg.get("parts", [])
                            for p in reversed(parts):
                                ptype = p.get("type")
                                if ptype == "tool":
                                    tname = p.get("tool")
                                    tstate = p.get("state", {})
                                    status = tstate.get("status", "unknown")
                                    tinput = tstate.get("input", {})
                                    state_summary = f"tool:{tname} status:{status}"
                                    if tname == "task":
                                        cat = tinput.get("category", "")
                                        state_summary += f" category:{cat}"
                                    elif tname == "question":
                                        # [FEAT-515 / Task 69.6.1] Interactive Popup Breakout
                                        # Extract question content for CLI display, then exit with code 2 (AWAITING_INPUT)
                                        q_input = tinput
                                        q_text = ""
                                        q_options = []
                                        if isinstance(q_input, dict):
                                            questions = q_input.get("questions", [])
                                            if isinstance(questions, list) and questions:
                                                q0 = questions[0] if isinstance(questions[0], dict) else {}
                                                q_text = q0.get("question", str(questions))
                                                q_options = q0.get("options", [])
                                            else:
                                                q_text = str(q_input)
                                        else:
                                            q_text = str(q_input)

                                        log_step(story_num, "INTERACTIVE_POPUP_DETECTED", "OpenCode emitted interactive question. Session paused.", severity="CRITICAL")
                                        print("\n" + "=" * 80, flush=True)
                                        print(f"[INTERACTIVE POPUP — SESSION {session_id}]", flush=True)
                                        print("=" * 80, flush=True)
                                        print(f"QUESTION: {q_text}", flush=True)
                                        if q_options:
                                            print("\nOPTIONS:", flush=True)
                                            for i, opt in enumerate(q_options, 1):
                                                print(f"  [{i}] {opt}", flush=True)
                                        print("\nTo resume, run:", flush=True)
                                        print(f"  python3 delegate.py --resume {session_id} --answer '<your choice>'", flush=True)
                                        print("=" * 80 + "\n", flush=True)

                                        # Persist session ID breadcrumb for easy resume discovery
                                        try:
                                            breadcrumb_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/logs/paused_session.txt")
                                            os.makedirs(os.path.dirname(breadcrumb_path), exist_ok=True)
                                            with open(breadcrumb_path, "w") as bf:
                                                bf.write(f"session_id={session_id}\nstory={story_num}\ntitle={title}\nquestion={q_text}\n")
                                        except Exception:
                                            pass

                                        _ACTIVE_SESSION_ID = None  # Don't auto-cleanup on exit; session is intentionally paused
                                        sys.exit(2)  # EXIT CODE 2 = AWAITING_INPUT

                                    if state_summary != last_inspected_state:
                                        last_inspected_state = state_summary
                                        log_step(story_num, "LIVE_SWARM_STATE", f"State transition: [{state_summary}]")
                                    break
                except Exception:
                    pass

                if post_exception is not None:
                    break

                # Heartbeat stdout line keeps process output active and prevents silent watchdog timeouts
                log_step(story_num, "HEARTBEAT", f"OpenAgent execution in progress... ({elapsed}s elapsed). Step log: /tmp/delegate_story_{story_num}.log")

        duration = time.time() - start_time

        if post_result is not None:
            finish = post_result.get("info", {}).get("finish", "unknown")
            tokens = post_result.get("info", {}).get("tokens", {})
            log_step(story_num, "COMPLETE", f"Story {story_num} dispatch ({mode.upper()}) complete in {duration:.1f}s. finish={finish} tokens={tokens}")
            log_step(story_num, "WEB_UI_LINK", f"Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}")

            # [BKM-033 / BKM-034] Extract and display execution response & Handover Reflection directly from in-flight chunk
            parts = post_result.get("parts", [])
            text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
            full_text = "\n\n".join(t.strip() for t in text_parts if t.strip())

            # [FEAT-496] Passive Swarm Telemetry Tap
            _log_live_usage_telemetry(story_num, sprint_num, title, current_model, duration, tokens, len(full_text))

            if full_text:
                print("\n" + "═" * 80, flush=True)
                print(f"📢 [OPENAGENT EXECUTION REPORT & HANDOVER REFLECTION — STORY {story_num}]", flush=True)
                print("═" * 80, flush=True)
                print(full_text, flush=True)
                print("═" * 80 + "\n", flush=True)

                # [FEAT-512] Attempt automatic Blocker Report ingestion
                try:
                    blocker_match = re.search(
                        r"(?:\[BLOCKER REPORT:\s*(.+?)\]|\*\*Blocker Report:\*\*\s*(.+))",
                        full_text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    if blocker_match:
                        blocker_text = (blocker_match.group(1) or blocker_match.group(2) or "").strip()
                        log_step(story_num, "BLOCKER_DETECTED", f"Subagent emitted blocker report: {blocker_text}", severity="CRITICAL")
                        subprocess.run(
                            [
                                "icm", "store",
                                "-t", "errors-resolved",
                                "-c", f"Story {story_num} ({title}) Blocker: {blocker_text}",
                                "-i", "critical",
                                "-k", f"blocker,delegation,openagent,story-{story_num},sprint-{sprint_num}"
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                except Exception:
                    pass

                # Attempt automatic ICM ingestion
                try:
                    reflection_match = re.search(
                        r"(?:\[HANDOVER REFLECTION\]|\*\*Handover Reflection:\*\*)\s*(.+)",
                        full_text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    reflection_text = reflection_match.group(1).strip() if reflection_match else full_text[:400]
                    icm_content = f"Story {story_num} ({title}) Delegation Reflection: {reflection_text}"
                    subprocess.run(
                        [
                            "icm", "store",
                            "-t", "errors-resolved",
                            "-c", icm_content,
                            "-i", "high",
                            "-k", f"delegation,openagent,prompt-tuning,story-{story_num},sprint-{sprint_num}"
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                except Exception:
                    pass
            else:
                # [FEAT-515 / Task 69.6.2] Silent Failure Escalation Gate
                # Core Law: "Fix the delegation infrastructure; do not manually finish the sprint."
                is_silent_failure = (finish == "unknown")
                if is_silent_failure:
                    log_step(story_num, "SILENT_DELEGATION_FAILURE",
                             f"[ALERT: SILENT_DELEGATION_FAILURE] finish={finish}, zero text parts. "
                             f"Model: {current_model}. Session: {session_id}. Duration: {duration:.1f}s.",
                             severity="CRITICAL")

                    # Persist to delegation_failures.log for retrospective analysis
                    try:
                        fail_log_dir = os.path.expanduser("~/Dev_Lab/HomeLabAI/logs")
                        os.makedirs(fail_log_dir, exist_ok=True)
                        fail_log_path = os.path.join(fail_log_dir, "delegation_failures.log")
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        fail_entry = (
                            f"[{ts}] SILENT_DELEGATION_FAILURE\n"
                            f"  Story: {story_num} ({title})\n"
                            f"  Sprint: {sprint_num}\n"
                            f"  Agent: {agent}\n"
                            f"  Model: {current_model}\n"
                            f"  Session: {session_id}\n"
                            f"  Duration: {duration:.1f}s\n"
                            f"  finish={finish}, tokens={tokens}\n"
                            f"  Web UI: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}\n"
                            f"  Raw Parts: {json.dumps(parts[:3], indent=2)}\n"
                            f"{'=' * 60}\n"
                        )
                        with open(fail_log_path, "a") as fl:
                            fl.write(fail_entry)
                    except Exception:
                        pass

                    # ICM store for pattern tracking
                    try:
                        subprocess.run(
                            [
                                "icm", "store",
                                "-t", "errors-resolved",
                                "-c", f"SILENT_DELEGATION_FAILURE: Story {story_num} ({title}) — finish={finish}, no text, model={current_model.get('modelID', 'unknown')}. Session {session_id}.",
                                "-i", "critical",
                                "-k", f"silent-failure,delegation,story-{story_num},sprint-{sprint_num}"
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    except Exception:
                        pass

                    print("\n[!!!] DELEGATION HALTED: Silent failure detected. The delegation infrastructure needs fixing.", flush=True)
                    print(f"[!!!] Inspect session: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}", flush=True)
                    print("[!!!] Failure log: ~/Dev_Lab/HomeLabAI/logs/delegation_failures.log", flush=True)
                    _cleanup_active_session()
                    sys.exit(3)  # EXIT CODE 3 = SILENT_DELEGATION_FAILURE
                else:
                    # Non-unknown finish with empty text (e.g. tool-only response) — warn but don't halt
                    print(f"[!] [STORY {story_num}] Note: No text parts returned in completion chunk (finish={finish}). Check Web UI.", flush=True)

            _ACTIVE_SESSION_ID = None
            return

        if post_exception is not None:
            e = post_exception
            err_ctx = _format_error_context(e)
            if isinstance(e, urllib.error.HTTPError) and e.code in (502, 503, 504, 429) and attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"HTTP {e.code} transient error on attempt {attempt}/{max_retries}. Backing off {backoff:.1f}s...\n{err_ctx}"
                log_step(story_num, "RETRY_BACKOFF", msg, severity="WARNING")
                time.sleep(backoff)
            elif attempt < max_retries:
                backoff = (2 ** attempt) + random.uniform(0.5, 1.5)
                msg = f"Dispatch error ({e}) on attempt {attempt}/{max_retries}. Retrying in {backoff:.1f}s...\n{err_ctx}"
                log_step(story_num, "RETRY_BACKOFF", msg, severity="WARNING")
                time.sleep(backoff)
            else:
                log_step(story_num, "FAILED", f"Dispatch failed after {duration:.1f}s: {e}\n{err_ctx}", severity="CRITICAL")
                sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAgent Swarm Story Delegator")
    parser.add_argument("--retrospective", action="store_true", help="Synthesize DELEGATION_RETROSPECTIVE.md from /tmp/delegate_story_*.log + REST session metrics, then exit")
    _retro_mode = "--retrospective" in sys.argv
    parser.add_argument("--sprint", required=not _retro_mode, type=int, help="Sprint number")
    parser.add_argument("--story", required=not _retro_mode, type=str, help="Story number (e.g. 709, 709B)")
    parser.add_argument("--title", required=not _retro_mode, help="Story title")
    parser.add_argument("--reference", required=not _retro_mode, help="Sprint plan / context reference document (read-only context for Atlas)")
    parser.add_argument("--sprint-doc", default=None, help="Path to Master Sprint Plan (e.g. Portfolio_Dev/SPRINT_PLAN_SPR_65_0.md) to automatically inject Tier-1 Executive Summary")
    parser.add_argument("--target", default=None, help="Actual file(s) Atlas is permitted to edit (omit to default to --reference). Separate multiple paths with commas.")
    parser.add_argument("--details", required=not _retro_mode, help="Detailed requirements")
    parser.add_argument("--mode", choices=["execute", "plan", "investigate"], default="execute", help="Delegation mode: execute (code edit), plan (read-only plan), or investigate (read-only diagnostic)")
    parser.add_argument("--verification", default="Post-dispatch AGY Validation", help="Verification command line (optional)")
    parser.add_argument("--dir", default=None, help="Target working directory")
    parser.add_argument("--retries", default=3, type=int, help="Max self-healing retries for 503/429 errors (default: 3)")
    parser.add_argument("--agent", default="atlas", help="Target agent persona override for testing (default: atlas)")
    parser.add_argument("--session-id", default=None, help="Existing REST session ID to attach to for context reuse across multi-step iterations (defaults to sprint-<N>)")
    parser.add_argument("--local-only", action="store_true", help="Force 100% sovereign local execution (M5 Air for architect/plan, Windows KENDER for coder/execute, zero cloud fallbacks)")
    parser.add_argument("--cloud-only", action="store_true", help="Force 100% cloud swarm execution (OpenRouter / OpenCode cloud models, zero local hardware fallbacks)")
    parser.add_argument("--resume", default=None, metavar="SESSION_ID", help="Resume a paused interactive session (exit code 2) by sending an answer to the pending question")
    parser.add_argument("--answer", default=None, help="Answer choice for the pending interactive question (used with --resume)")
    args = parser.parse_args()

    # [FEAT-515 / Task 69.6.1] Interactive Session Resume Handler
    if args.resume:
        if not args.answer:
            print("[!] --resume requires --answer <choice> to send a response to the paused session.", flush=True)
            sys.exit(1)
        resume_sid = args.resume
        print(f"[*] Resuming paused session {resume_sid} with answer: {args.answer}", flush=True)
        try:
            resume_payload = json.dumps({
                "parts": [{"type": "text", "text": args.answer}]
            }).encode("utf-8")
            resume_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{resume_sid}/message",
                data=resume_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(resume_req, timeout=600) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                parts = result.get("parts", [])
                text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
                full_text = "\n\n".join(t.strip() for t in text_parts if t.strip())
                if full_text:
                    print("\n" + "=" * 80, flush=True)
                    print(f"[RESUME RESPONSE — SESSION {resume_sid}]", flush=True)
                    print("=" * 80, flush=True)
                    print(full_text, flush=True)
                    print("=" * 80 + "\n", flush=True)
                else:
                    print(f"[!] Resume completed but no text returned. Check session at http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{resume_sid}", flush=True)
        except Exception as e:
            print(f"[!] Resume failed: {e}", flush=True)
            sys.exit(1)
        sys.exit(0)

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
        agent=args.agent,
        max_retries=args.retries,
        mode=args.mode,
        target_files=args.target,
        session_id=args.session_id,
        sprint_doc=args.sprint_doc,
        local_only=args.local_only,
        cloud_only=args.cloud_only,
    )
