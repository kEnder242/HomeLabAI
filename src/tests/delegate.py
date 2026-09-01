"""
[BKM-034 Point 12] OpenAgent Swarm REST Dispatcher & Cloud Quota Sentinel
Formalized launcher script for orchestrator-to-OpenAgent story delegation.
Dispatches dispatches through Atlas (Plan Executor, Groq 70b) and Sisyphus (Lead Orchestrator),
creating a clean REST session on port 4097, pre-checking cloud rate limits, and dispatching story prompts.
"""

import argparse
import json
import os
import re
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


def _log_live_usage_telemetry(story_num: int, sprint_num: int, title: str, model_obj: dict, duration: float, tokens: dict, text_len: int):
    """[FEAT-496] Passive Swarm Telemetry Tap for live_usage_stream.jsonl"""
    try:
        data_dir = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
        os.makedirs(data_dir, exist_ok=True)
        stream_path = os.path.join(data_dir, "live_usage_stream.jsonl")
        
        out_tokens = tokens.get("output", 0) if isinstance(tokens, dict) else 0
        if out_tokens == 0 and text_len > 0:
            out_tokens = max(1, int(text_len / 4.0))
            
        tp = round(out_tokens / duration, 2) if duration > 0 and out_tokens > 0 else 0.0
        provider_id = model_obj.get("providerID", "unknown") if isinstance(model_obj, dict) else "unknown"
        model_id = model_obj.get("modelID", "unknown") if isinstance(model_obj, dict) else str(model_obj)
        
        seat = "Cloud Swarm"
        if "4090" in provider_id or "kender" in provider_id:
            seat = "Windows KENDER (RTX 4090)"
        elif "m5" in provider_id or "mlx" in provider_id:
            seat = "Apple M5 Air"
        elif "z87" in provider_id or "vllm" in provider_id:
            seat = "Linux z87 (RTX 2080 Ti)"
            
        record = {
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": f"delegate.py (Story {story_num})",
            "task_title": title,
            "seat": seat,
            "provider": provider_id,
            "model": model_id,
            "tokens_generated": out_tokens,
            "duration_seconds": round(duration, 2),
            "throughput_tok_s": tp
        }
        with open(stream_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
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
def delegate(story_num, title, reference_file, details, verification, sprint_num=50, target_dir=None, agent="sisyphus", max_retries=3, mode="execute", target_files=None, session_id=None, sprint_doc=None, local_only=False):
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
You are Sisyphus (Ultraworker & Autonomous Engineer). Execute the code modifications directly and surgically.
TOOL GUIDANCE: Always call the clara-dna_safe_patch MCP tool for surgical code edits. For researching DNA specifications (FEAT, LAB, BKM, GEM, SCAR), query clara-dna_query_dna or bash `icm recall`. If safe_patch fails, report the failure immediately."""
        _edit_scope = target_files if target_files else reference_file
        note_block = f"[NOTE] Apply code modifications strictly to {_edit_scope}. Silicon validation and testing will be performed post-dispatch by the orchestrator."

    # [BKM-034 Two-Tier Payload Construction]
    effective_sprint_doc = sprint_doc or (reference_file if reference_file and "SPRINT_PLAN" in reference_file else None)
    sprint_summary = _extract_sprint_summary(effective_sprint_doc)
    tier1_block = ""
    if sprint_summary:
        tier1_block = f"""[TIER 1: GLOBAL SPRINT SITUATIONAL AWARENESS]
Sprint Reference: {effective_sprint_doc}
{sprint_summary}

(Directive: Read the full sprint plan on disk at '{effective_sprint_doc}' for deep context if needed, but restrict file edits strictly to your assigned target files.)

---
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

[HANDOVER REFLECTION]
As an execution peer, reflect candidly on how this task was handed over to you. In 2-3 natural sentences, tell me: What tripped you up, what turned out to be inaccurate or missing in the instructions, and what single change to the prompt would have made this execution faster?

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
                    log_step(story_num, "LOCAL_ONLY_MODE", "Enforcing 100% Sovereign Local Silicon (M5 Air + Windows KENDER). Zero cloud fallbacks.")
                    if mode in ("plan", "investigate") or agent in ("prometheus", "atlas", "architect"):
                        model_ladder = [local_cfg.get("architect", {"providerID": "my-m5-mlx", "modelID": "mlx-community--Qwen3.8-27B-4bit"})]
                    else:
                        model_ladder = [
                            local_cfg.get("coder", {"providerID": "my-windows-4090", "modelID": "qwen2.5-coder:14b"}),
                            local_cfg.get("fallback_coder", {"providerID": "my-m5-mlx", "modelID": "mlx-community--Qwen2.5-Coder-14B-Instruct-4bit"})
                        ]
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
        else:
            model_ladder = [
                {"providerID": "opencode", "modelID": "hy3-free"},
                {"providerID": "openrouter", "modelID": "openrouter/free"},
                {"providerID": "my-m5-mlx", "modelID": "mlx-community--Qwen3.8-27B-4bit"},
            ]

    # Pre-filter unreachable endpoints so we never block on 60s socket timeouts (unless in local_only mode where we report directly)
    if not local_only:
        model_ladder = [m for m in model_ladder if _is_provider_reachable(m.get("providerID", ""))]
        if not model_ladder:
            model_ladder = [{"providerID": "openrouter", "modelID": "openrouter/free"}]

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
                print(f"[!] [STORY {story_num}] Note: No text parts returned in completion chunk.", flush=True)

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
    parser.add_argument("--sprint", required=not _retro_mode, type=int, default=53, help="Sprint number (e.g. 53)")
    parser.add_argument("--story", required=not _retro_mode, type=int, help="Story number")
    parser.add_argument("--title", required=not _retro_mode, help="Story title")
    parser.add_argument("--reference", required=not _retro_mode, help="Sprint plan / context reference document (read-only context for Atlas)")
    parser.add_argument("--sprint-doc", default=None, help="Path to Master Sprint Plan (e.g. Portfolio_Dev/SPRINT_PLAN_SPR_65_0.md) to automatically inject Tier-1 Executive Summary")
    parser.add_argument("--target", default=None, help="Actual file(s) Atlas is permitted to edit (omit to default to --reference). Separate multiple paths with commas.")
    parser.add_argument("--details", required=not _retro_mode, help="Detailed requirements")
    parser.add_argument("--mode", choices=["execute", "plan", "investigate"], default="execute", help="Delegation mode: execute (code edit), plan (read-only plan), or investigate (read-only diagnostic)")
    parser.add_argument("--verification", default="Post-dispatch AGY Validation", help="Verification command line (optional)")
    parser.add_argument("--dir", default=None, help="Target working directory")
    parser.add_argument("--retries", default=3, type=int, help="Max self-healing retries for 503/429 errors (default: 3)")
    parser.add_argument("--agent", default="sisyphus", help="Target agent persona override for testing (default: sisyphus)")
    parser.add_argument("--session-id", default=None, help="Existing REST session ID to attach to for context reuse across multi-step iterations (defaults to sprint-<N>)")
    parser.add_argument("--local-only", action="store_true", help="Force 100% sovereign local execution (M5 Air for architect/plan, Windows KENDER for coder/execute, zero cloud fallbacks)")
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
        agent=args.agent,
        max_retries=args.retries,
        mode=args.mode,
        target_files=args.target,
        session_id=args.session_id,
        sprint_doc=args.sprint_doc,
        local_only=args.local_only,
    )
