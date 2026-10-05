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
SESSION_BREADCRUMB_FILE = "/tmp/active_openagent_sessions.json"
WARM_SESSION_FILE = "/tmp/active_warm_sessions.json"


def save_warm_session(agent: str, session_id: str):
    """[FEAT-648] Persist latest warm session ID for an agent across adjacent stories."""
    data = {}
    if os.path.exists(WARM_SESSION_FILE):
        try:
            with open(WARM_SESSION_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[agent] = {
        "session_id": session_id,
        "timestamp": time.time(),
    }
    try:
        with open(WARM_SESSION_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def get_warm_session(agent: str, max_age_seconds: float = 1800.0) -> str | None:
    """[FEAT-648] Retrieve valid unexpired warm session ID for an agent."""
    if not os.path.exists(WARM_SESSION_FILE):
        return None
    try:
        with open(WARM_SESSION_FILE, "r") as f:
            data = json.load(f)
        entry = data.get(agent)
        if entry and isinstance(entry, dict):
            if time.time() - entry.get("timestamp", 0) <= max_age_seconds:
                return entry.get("session_id")
    except Exception:
        pass
    return None


def _register_active_session(session_id: str, title: str = "", agent: str = ""):
    """[FEAT-556 / BKM-049 / FEAT-648] Register active PID and session ID in breadcrumbs & warm session cache."""
    global _ACTIVE_SESSION_ID
    _ACTIVE_SESSION_ID = session_id
    if agent:
        save_warm_session(agent, session_id)
    try:
        data = {}
        if os.path.exists(SESSION_BREADCRUMB_FILE):
            try:
                with open(SESSION_BREADCRUMB_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[str(os.getpid())] = {
            "session_id": session_id,
            "title": title,
            "timestamp": time.time(),
        }
        with open(SESSION_BREADCRUMB_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _unregister_active_session():
    """Remove current PID from breadcrumbs on clean exit."""
    global _ACTIVE_SESSION_ID
    _ACTIVE_SESSION_ID = None
    try:
        if os.path.exists(SESSION_BREADCRUMB_FILE):
            with open(SESSION_BREADCRUMB_FILE, "r") as f:
                data = json.load(f)
            pid_str = str(os.getpid())
            if pid_str in data:
                del data[pid_str]
                with open(SESSION_BREADCRUMB_FILE, "w") as f:
                    json.dump(data, f)
    except Exception:
        pass


def _reap_orphaned_sessions():
    """[FEAT-556 / BKM-049] Check breadcrumbs for dead PIDs and abort their orphaned OpenCode sessions."""
    if not os.path.exists(SESSION_BREADCRUMB_FILE):
        return
    try:
        with open(SESSION_BREADCRUMB_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return

        reaped = []
        remaining = {}
        for pid_str, entry in data.items():
            try:
                pid = int(pid_str)
                # Check if process is still alive
                os.kill(pid, 0)
                remaining[pid_str] = entry
            except (OSError, ProcessLookupError, ValueError):
                # Process is dead! Reap its session on port 4097
                sid = entry.get("session_id")
                if sid:
                    try:
                        req_abort = urllib.request.Request(
                            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{sid}/abort",
                            method="POST",
                        )
                        urllib.request.urlopen(req_abort, timeout=0.8)
                        reaped.append(sid)
                    except Exception:
                        pass

        with open(SESSION_BREADCRUMB_FILE, "w") as f:
            json.dump(remaining, f)

        if reaped:
            print(f"🧹 [ORPHAN REAPER] Aborted {len(reaped)} orphaned OpenAgent session(s) from dead tasks: {reaped}", flush=True)
    except Exception:
        pass


def _trigger_ambient_hook_telemetry(
    story_num: str, title: str, duration: float, status: str = "SUCCESS"
) -> dict:
    """[FEAT-650] Execute ambient hook telemetry at the conclusion of story delegation.
    Surfaces Grounding Header and JITC memory state even in headless / non-interactive runs.
    """
    hook_script = os.path.expanduser("~/.gemini/config/scripts/ambient_hook.sh")
    if not os.path.exists(hook_script):
        hook_script = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config/scripts/ambient_hook.sh",
            )
        )
    
    if not os.path.exists(hook_script):
        return {"status": "SKIPPED", "reason": "hook_script_not_found"}

    payload = {
        "invocationNum": 1,
        "userMessage": f"Story {story_num}: {title} ({status}, {duration:.1f}s)",
    }
    try:
        p = subprocess.run(
            [hook_script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if p.returncode == 0:
            res = json.loads(p.stdout)
            steps = res.get("injectSteps", [])
            for step in steps:
                text = step.get("text", "")
                if "🧬" in text or "Grounding" in text:
                    print("\n" + "-" * 70, flush=True)
                    print(f"📡 [AMBIENT HOOK TELEMETRY] Story {story_num} Memory Reflection:", flush=True)
                    print(text[:400], flush=True)
                    print("-" * 70 + "\n", flush=True)
            return {"status": "SUCCESS", "injectSteps": steps, "raw": res}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}
    return {"status": "FAILED"}



def _nuke_all_sessions():
    """[BKM-034] Unconditionally abort all in-flight and orphaned sessions on OpenCode REST port 4097."""
    try:
        req_list = urllib.request.Request(
            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session"
        )
        with urllib.request.urlopen(req_list, timeout=1.5) as resp:
            sessions = json.loads(resp.read().decode("utf-8"))
        if isinstance(sessions, list):
            for s in sessions:
                sid = s.get("id")
                if sid:
                    try:
                        req_abort = urllib.request.Request(
                            f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{sid}/abort",
                            method="POST",
                        )
                        urllib.request.urlopen(req_abort, timeout=0.8)
                    except Exception:
                        pass
    except Exception:
        pass


def _cleanup_active_session():
    """Auto-abort and delete all in-flight REST sessions on task termination or exit."""
    global _ACTIVE_SESSION_ID
    if _ACTIVE_SESSION_ID:
        try:
            req_abort = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{_ACTIVE_SESSION_ID}/abort",
                method="POST",
            )
            urllib.request.urlopen(req_abort, timeout=0.8)
        except Exception:
            pass
    _unregister_active_session()


def _sig_term_handler(signum, frame):
    _cleanup_active_session()
    sys.exit(1)


signal.signal(signal.SIGINT, _sig_term_handler)
signal.signal(signal.SIGTERM, _sig_term_handler)
atexit.register(_cleanup_active_session)

# Automatic startup orphan sweep on port 4097
_reap_orphaned_sessions()


def _log_pager_event(message: str, severity: str = "WARNING"):
    """Log telemetry event to pager_activity.json for real-time status.html/pager.html visibility."""
    pager_path = os.path.expanduser(
        "~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json"
    )
    if not os.path.exists(os.path.dirname(pager_path)):
        return
    try:
        events = []
        if os.path.exists(pager_path):
            with open(pager_path, "r") as f:
                events = json.load(f)
        events.insert(
            0,
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message,
                "severity": severity,
                "source": "delegate.py",
            },
        )
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


def _extract_telemetry_knobs(
    target_scope: str = "",
    model_name: str = "",
    status: str = "",
    error_reason: str = "",
    agent_role: str = "",
) -> dict:
    """[FEAT-552] Extract OpenCode, OpenAgent, Infrastructure, Headroom, and Task configuration knobs for matrix scorecard."""
    knobs = {
        "compaction_auto": False,
        "compaction_prune": False,
        "routes_through_headroom": False,
        "model_configured_context": 0,
        "active_mcp_servers": [],
        "active_plugins": [],
        "disabled_tools": [],
        "disabled_agents": [],
        "agent_role": agent_role or "unknown",
        "agent_role_model": "unknown",
        "primary_thought_node": "unknown",
        "active_thought_lora": None,
        "server_kv_mode": "unknown",
        "server_drafter": "none",
        "server_chunked_prefill": False,
        "task_archetype": "safe_patch",
        "language_target": "python",
        "failure_bucket": "SUCCESS" if status.upper() == "SUCCESS" else "UNKNOWN",
    }

    # 1. Parse client configuration from opencode.json
    opencode_cfg_path = os.path.expanduser("~/Dev_Lab/opencode.json")
    if os.path.exists(opencode_cfg_path):
        try:
            with open(opencode_cfg_path, "r") as cf:
                content = cf.read()
                clean_lines = [
                    l for l in content.splitlines() if not l.strip().startswith("//")
                ]
                cfg = json.loads("\n".join(clean_lines))

                comp = cfg.get("compaction", {})
                knobs["compaction_auto"] = comp.get("auto", True)
                knobs["compaction_prune"] = comp.get("prune", True)
                knobs["active_plugins"] = cfg.get("plugin", [])

                mcp = cfg.get("mcp", {})
                knobs["active_mcp_servers"] = [
                    k
                    for k, v in mcp.items()
                    if isinstance(v, dict) and v.get("enabled", True)
                ]

                providers = cfg.get("provider", {})
                for p_name, p_info in providers.items():
                    base_url = p_info.get("options", {}).get("baseURL", "")
                    if "8002" in base_url and (
                        "m5" in model_name.lower() or "mlx" in model_name.lower()
                    ):
                        knobs["routes_through_headroom"] = True
                    models = p_info.get("models", {})
                    for m_id, m_data in models.items():
                        if m_id in model_name or model_name in m_id:
                            knobs["model_configured_context"] = m_data.get(
                                "limit", {}
                            ).get("context", 0)
        except Exception:
            pass

    # 2. Parse OpenAgent swarm configuration from oh-my-openagent.json
    omo_cfg_paths = [
        os.path.expanduser("~/.config/opencode/oh-my-openagent.json"),
        os.path.expanduser("~/Dev_Lab/oh-my-openagent.json"),
    ]
    for omo_path in omo_cfg_paths:
        if os.path.exists(omo_path):
            try:
                with open(omo_path, "r") as omo_f:
                    omo_cfg = json.load(omo_f)
                    knobs["disabled_tools"] = omo_cfg.get("disabled_tools", [])
                    knobs["disabled_agents"] = omo_cfg.get("disabled_agents", [])
                    if agent_role and agent_role in omo_cfg.get("agents", {}):
                        knobs["agent_role_model"] = omo_cfg["agents"][agent_role].get(
                            "model", "unknown"
                        )
                break
            except Exception:
                pass

    # 3. Parse Infrastructure configuration from infrastructure.json
    infra_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")
    if os.path.exists(infra_path):
        try:
            with open(infra_path, "r") as inf_f:
                inf_cfg = json.load(inf_f)
                knobs["primary_thought_node"] = (
                    inf_cfg.get("nodes", {})
                    .get("thought", {})
                    .get("primary", "unknown")
                )
                knobs["active_thought_lora"] = (
                    inf_cfg.get("nodes", {}).get("thought", {}).get("lora_name")
                )
        except Exception:
            pass

    # 4. Probe server-side Headroom state (Port 8002)
    try:
        req = urllib.request.Request("http://192.168.1.46:8002/status")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            hdata = json.loads(resp.read().decode("utf-8"))
            knobs["server_kv_mode"] = hdata.get("mode", "unknown")
            knobs["server_drafter"] = hdata.get("drafter") or "none"
            knobs["server_chunked_prefill"] = hdata.get("chunked_prefill", False)
    except Exception:
        pass

    # 5. Derive task archetype & language target
    if target_scope:
        targets = [t.strip() for t in target_scope.split(",") if t.strip()]
        if any("test" in t.lower() for t in targets):
            knobs["task_archetype"] = "test_suite"
        elif any(not os.path.exists(t) for t in targets):
            knobs["task_archetype"] = "greenfield"
        else:
            knobs["task_archetype"] = "safe_patch"

        if any(t.endswith(".js") for t in targets):
            knobs["language_target"] = "javascript"
        elif any(t.endswith(".html") or t.endswith(".css") for t in targets):
            knobs["language_target"] = "html_css"
        elif any(t.endswith(".md") for t in targets):
            knobs["language_target"] = "markdown"

    # 6. Classify failure bucket
    if status.upper() != "SUCCESS":
        err_lower = (error_reason or "").lower()
        if "context" in err_lower or "exceed" in err_lower or "n_ctx" in err_lower:
            knobs["failure_bucket"] = "CONTEXT_OVERFLOW"
        elif "timeout" in err_lower or "504" in err_lower:
            knobs["failure_bucket"] = "SOCKET_TIMEOUT"
        elif "compaction" in err_lower:
            knobs["failure_bucket"] = "COMPACTION_LOOP"
        elif (
            "gateway" in err_lower
            or "502" in err_lower
            or "forwarding failed" in err_lower
        ):
            knobs["failure_bucket"] = "GATEWAY_DISCONNECT"
        elif "reject" in err_lower or "tool" in err_lower:
            knobs["failure_bucket"] = "TOOL_REJECTION"
        else:
            knobs["failure_bucket"] = "PROVIDER_ERROR"

    return knobs


def _log_delegation_ledger(
    sprint_num: int,
    story_num: any,
    title: str,
    mode: str,
    tier: str,
    target_scope: str,
    session_id: str,
    duration_s: float,
    tokens: dict,
    status: str,
    attempts: int = 1,
    verification_cmd: str = "",
    verification_passed: bool = False,
    error_reason: str = "",
    model_name: str = "",
    agent_role: str = "",
    reflection: str = "",
    live_gate_status: str = "UNSPECIFIED",
    live_gate_details: str = "",
):
    """[FEAT-552 / BKM-049 / FEAT-654] Record structured delegation execution to persistent delegation_ledger.jsonl and ICM."""
    knobs = _extract_telemetry_knobs(
        target_scope, model_name, status, error_reason, agent_role=agent_role
    )

    ledger_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sprint": sprint_num,
        "story": str(story_num),
        "title": title,
        "mode": mode,
        "tier": tier,
        "target_scope": target_scope or "",
        "session_id": session_id or "",
        "duration_s": round(duration_s, 2),
        "tokens": tokens or {},
        "status": status,
        "attempts": attempts,
        "verification_cmd": verification_cmd or "",
        "verification_passed": verification_passed,
        "error_reason": error_reason or "",
        "model": model_name or "unknown",
        "reflection": reflection or "",
        "live_gate_status": live_gate_status,
        "live_gate_details": live_gate_details,
        "knobs": knobs,
    }
    line = json.dumps(ledger_entry) + "\n"
    paths = [
        os.path.expanduser("~/Dev_Lab/HomeLabAI/data/delegation_ledger.jsonl"),
        os.path.expanduser(
            "~/Dev_Lab/Portfolio_Dev/field_notes/data/delegation_ledger.jsonl"
        ),
    ]
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a") as f:
                f.write(line)
        except Exception:
            pass

    # [BKM-049 Feedback Loop] Ingest handover reflection into persistent ICM
    if reflection and reflection.strip():
        try:
            icm_bin = os.path.expanduser("~/.local/bin/icm")
            if not os.path.exists(icm_bin):
                icm_bin = "icm"
            icm_content = f"Story {story_num} ({title}) [{tier} via {model_name}]: {reflection.strip()}"
            subprocess.run(
                [icm_bin, "store", "-t", "delegation_feedback", "-c", icm_content],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass


def show_delegation_ledger(limit: int = 20):
    """Display the recent delegation history ledger from delegation_ledger.jsonl."""
    ledger_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/data/delegation_ledger.jsonl")
    if not os.path.exists(ledger_path):
        ledger_path = os.path.expanduser(
            "~/Dev_Lab/Portfolio_Dev/field_notes/data/delegation_ledger.jsonl"
        )
    if not os.path.exists(ledger_path):
        print("ℹ️ No delegation ledger entries recorded yet.")
        return

    entries = []
    try:
        with open(ledger_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception as e:
        print(f"❌ Error reading delegation ledger: {e}")
        return

    if not entries:
        print("ℹ️ Delegation ledger is empty.")
        return

    recent = entries[-limit:]
    print("=" * 110)
    print(
        f"📜 DELEGATION EXECUTION LEDGER (Showing last {len(recent)} of {len(entries)} entries)"
    )
    print("=" * 110)
    print(
        f"{'TIMESTAMP':<19} | {'SPR':<6} | {'STORY':<8} | {'TIER':<10} | {'STATUS':<16} | {'LIVE_GATE':<12} | {'DUR(s)':<7} | {'MODEL'}"
    )
    print("-" * 115)

    local_total = 0
    local_success = 0
    cloud_total = 0
    cloud_success = 0

    for e in entries:
        tier = e.get("tier", "")
        status = e.get("status", "")
        is_success = status == "SUCCESS"
        if "LOCAL" in tier:
            local_total += 1
            if is_success:
                local_success += 1
        elif "CLOUD" in tier:
            cloud_total += 1
            if is_success:
                cloud_success += 1

    for r in recent:
        ts = r.get("timestamp", "")[:19]
        spr = f"SPR-{r.get('sprint', '?')}"
        sty = str(r.get("story", "?"))[:8]
        tier = r.get("tier", "?")[:10]
        status = r.get("status", "?")[:16]
        lg_status = r.get("live_gate_status", "UNSPECIFIED")[:12]
        dur = f"{r.get('duration_s', 0):.1f}"
        model = str(r.get("model", "?"))[:25]
        print(
            f"{ts:<19} | {spr:<6} | {sty:<8} | {tier:<10} | {status:<16} | {lg_status:<12} | {dur:<7} | {model}"
        )

    print("=" * 110)
    print("📊 HISTORICAL AGGREGATE SUMMARY:")
    l_rate = (local_success / local_total * 100) if local_total else 0.0
    c_rate = (cloud_success / cloud_total * 100) if cloud_total else 0.0
    print(
        f"  [SWARM:LOCAL] Runs: {local_total:<4} | Successes: {local_success:<4} | Success Rate: {l_rate:.1f}%"
    )
    print(
        f"  [SWARM:CLOUD] Runs: {cloud_total:<4} | Successes: {cloud_success:<4} | Success Rate: {c_rate:.1f}%"
    )
    print("=" * 110)


def _load_agent_rules(agent_name: str) -> str:
    """[Story 99.0 / BKM-049] Dynamically load and inline the appropriate AGENTS_L*.md rule file."""
    rule_file = "AGENTS_L2.md" if agent_name in ["atlas", "Atlas"] else "AGENTS_L3.md"
    search_paths = [
        os.path.expanduser(f"~/Dev_Lab/{rule_file}"),
        os.path.join(os.getcwd(), rule_file),
        os.path.abspath(os.path.join(os.path.dirname(__file__), f"../../../{rule_file}")),
    ]
    for p in search_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
    return ""


def _probe_mcp_server() -> tuple[bool, str]:
    """[Story 99.0 / BKM-024 / FEAT-486 / FEAT-658] Fast stdio JSON-RPC + OpenCode REST /mcp verification with auto-healing."""
    mcp_script = "/home/jallred/AcmeLab/src/clara_dna_mcp_server.py"
    py_bin = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
    if not os.path.exists(mcp_script) or not os.path.exists(py_bin):
        return False, f"MCP script or Python binary missing ({mcp_script})"
    try:
        proc = subprocess.Popen(
            [py_bin, mcp_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "delegate_probe", "version": "1.0"}},
        }) + "\n"
        proc.stdin.write(init_req)
        proc.stdin.flush()
        resp_line = proc.stdout.readline()
        proc.terminate()
        if not (resp_line and "result" in json.loads(resp_line)):
            return False, f"Unexpected response from MCP server: {resp_line}"
    except Exception as e:
        return False, f"MCP subprocess probe error: {e}"

    # Verify OpenCode REST /mcp endpoint status
    def _check_opencode_mcp():
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{OPENCODE_REST_PORT}/mcp", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                clara_status = data.get("clara-dna", {}).get("status")
                return clara_status == "connected", clara_status
        except Exception as e:
            return False, str(e)

    is_connected, status_val = _check_opencode_mcp()
    if is_connected:
        return True, "OK"

    # Auto-heal: restart opencode-core.service if connection dropped or failed
    try:
        log_step(0, "MCP_AUTO_HEAL", f"OpenCode MCP status is '{status_val}'. Restarting opencode-core.service...", severity="WARNING")
        subprocess.run(["systemctl", "--user", "restart", "opencode-core.service"], check=False)
        for _ in range(6):
            time.sleep(1.0)
            is_conn, stat = _check_opencode_mcp()
            if is_conn:
                return True, "OK (auto-healed opencode-core.service)"
        return False, f"OpenCode MCP status remained '{stat}' after auto-heal restart"
    except Exception as e:
        return False, f"Auto-heal failed: {e}"


def check_cloud_quota(provider="opencode"):
    """
    [FEAT-Q01] Quick cloud quota & rate limit sentinel check.
    Pings provider status and notifies orchestrator of rate-limit reset windows.
    """
    print(
        f"[*] Pre-flight check: Probing {provider} cloud endpoint status...", flush=True
    )
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
                print(
                    f"[+] OpenCode core engine listening on port {OPENCODE_REST_PORT}. Temp session: {session_id}",
                    flush=True,
                )
                # [CLEANUP] Purge temporary probe session so it does not leave an empty "New session" entry in OpenCode dashboard
                try:
                    del_req = urllib.request.Request(
                        f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}",
                        method="DELETE",
                    )
                    with urllib.request.urlopen(del_req, timeout=3):
                        pass
                except Exception:
                    pass
                return True
    except Exception as e:
        print(f"[!] Warning: OpenCode core engine check failed: {e}", flush=True)
        _log_pager_event(
            f"OpenCode core engine pre-flight probe failed: {e}", severity="WARNING"
        )
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
        print(
            "[*] [WOL] Sent Wake-on-LAN Magic Packet to M5-Air (192.168.1.46).",
            flush=True,
        )
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
    print(
        f"[*] Waking web UI via socket touch on port {OPENCODE_WEB_PORT}...", flush=True
    )
    try:
        req = urllib.request.Request(OPENCODE_WEB_URL)
        with urllib.request.urlopen(req, timeout=10):
            pass
        print(
            f"[+] Web UI live at http://192.168.1.238:{OPENCODE_WEB_PORT}/", flush=True
        )
    except Exception as e:
        print(f"[~] Web UI touch attempted (may need a moment): {e}", flush=True)


def _extract_sprint_summary(sprint_doc_path: str) -> str:
    """[BKM-034 Tier 1] Extract the Executive Summary & Architectural Contract from a sprint plan."""
    if not sprint_doc_path or not os.path.exists(sprint_doc_path):
        return ""
    try:
        with open(sprint_doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(
            r"## 🧭 Executive Summary & Architectural Contract(.*?)(?=## 📋 Granular Story Breakdown|\Z)",
            content,
            re.DOTALL,
        )
        if match:
            summary = match.group(1).strip()
            if len(summary) > 2500:
                summary = (
                    summary[:2500]
                    + "\n...(truncated for prompt efficiency, see full doc on disk)"
                )
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
                    err_name = body_json.get("name") or body_json.get("error", {}).get(
                        "type", "Error"
                    )
                    err_msg = (
                        body_json.get("data", {}).get("message")
                        or body_json.get("error", {}).get("message")
                        or str(body_json)
                    )
                    err_ref = body_json.get("data", {}).get("ref") or body_json.get(
                        "ref", ""
                    )
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
                    [
                        "journalctl",
                        "--user",
                        "-u",
                        "opencode-core.service",
                        "-n",
                        "3",
                        "--no-pager",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if res.stdout:
                    jlines = [
                        line.strip()
                        for line in res.stdout.strip().splitlines()
                        if line.strip()
                    ]
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
        m5_status = (
            "UP" if s.connect_ex(("192.168.1.46", 8002)) == 0 else "DOWN/REFUSED"
        )
        s.close()
    except Exception:
        m5_status = "ERROR"

    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        w4090_status = (
            "UP" if s.connect_ex(("192.168.1.26", 11434)) == 0 else "DOWN/REFUSED"
        )
        s.close()
    except Exception:
        w4090_status = "ERROR"

    details.append(
        f"  └─ Silicon Reachability: M5(8002)={m5_status} | 4090(11434)={w4090_status}"
    )
    return "\n".join(details)


def _ping_host(host: str, port: int, timeout: float = 0.5) -> bool:
    """Fast socket reachability probe for federated silicon endpoints."""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        ok = s.connect_ex((host, port)) == 0
        s.close()
        return ok
    except Exception:
        return False


def _log_live_usage_telemetry(
    story_num: int,
    sprint_num: int,
    title: str,
    model_obj: dict,
    duration: float,
    tokens: dict,
    text_len: int,
    raw_tp: float = None,
):
    """[FEAT-498] Unified Swarm Telemetry Tap for live_usage_stream.jsonl & cumulative_tokens.json"""
    try:
        from infra.cumulative_telemetry import log_telemetry_event

        out_tokens = tokens.get("output", 0) if isinstance(tokens, dict) else 0
        if out_tokens == 0 and text_len > 0:
            out_tokens = max(1, int(text_len / 4.0))

        provider_id = (
            model_obj.get("providerID", "unknown")
            if isinstance(model_obj, dict)
            else "unknown"
        )
        model_id = (
            model_obj.get("modelID", "unknown")
            if isinstance(model_obj, dict)
            else str(model_obj)
        )

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
            raw_throughput_tok_s=raw_tp,
        )
    except Exception:
        pass


def _is_provider_reachable(provider_id: str) -> bool:
    """Pre-probes local silicon endpoints (0.8s timeout) to avoid 60s OpenCode HTTP socket stalls."""
    if "4090" in provider_id or "kender" in provider_id or "windows" in provider_id:
        return _ping_host("192.168.1.26", 11434, timeout=0.5)
    if "m5" in provider_id or "mlx" in provider_id:
        return _ping_host("192.168.1.46", 8002, timeout=0.5)
    return True


def _run_bkm049_diagnostics(
    story_num: int, attempt: int, reason: str = "", session_id: str | None = None
) -> dict:
    """[BKM-049] Mandatory Three-Tier Diagnostic Probes between execution retries.
    1. Server & Silicon State (Port 4097, Port 8002/8000, GPU/sockets)
    2. Session Transcripts & Messages (OpenCode REST messages, compaction loops, tool rejections)
    3. Harness & Configuration Audit
    """
    sid = session_id or _ACTIVE_SESSION_ID
    diag = {
        "story": story_num,
        "attempt": attempt,
        "reason": reason,
        "session_id": sid,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "opencode_rest": _ping_host("127.0.0.1", OPENCODE_REST_PORT),
        "m5_silicon": _ping_host("192.168.1.46", 8002)
        or _ping_host("192.168.1.46", 8000),
        "w4090_silicon": _ping_host("192.168.1.26", 11434),
        "session_turns": 0,
        "session_errors": [],
    }

    # Deep Session Message Inspection via REST
    if sid and diag["opencode_rest"]:
        try:
            m_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{sid}/message"
            )
            with urllib.request.urlopen(m_req, timeout=3.0) as m_resp:
                msgs = json.loads(m_resp.read().decode("utf-8"))
                diag["session_turns"] = len(msgs)

                # Scan messages for compaction loops, provider errors, and tool failures
                for m in msgs[-15:]:
                    for p in m.get("parts", []):
                        t = p.get("text", "")
                        if (
                            "exceeded" in t.lower()
                            or "limit" in t.lower()
                            or "error" in t.lower()
                            or "compaction" in t.lower()
                        ):
                            snip = t.strip()[:180]
                            if snip not in diag["session_errors"]:
                                diag["session_errors"].append(snip)
        except Exception:
            pass

    try:
        j_res = subprocess.run(
            [
                "journalctl",
                "--user",
                "-u",
                "opencode-core.service",
                "-n",
                "3",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        diag["journal_tail"] = (
            j_res.stdout.strip().splitlines()[-2:] if j_res.stdout else []
        )
    except Exception:
        diag["journal_tail"] = []

    err_summary = (
        f" | Errors: {diag['session_errors'][:2]}" if diag["session_errors"] else ""
    )
    summary_str = (
        f"[BKM-049 DIAGNOSTIC] Attempt {attempt} ({reason}): "
        f"REST:4097={'UP' if diag['opencode_rest'] else 'DOWN'} | "
        f"M5:8002={'UP' if diag['m5_silicon'] else 'DOWN'} | "
        f"W4090:11434={'UP' if diag['w4090_silicon'] else 'DOWN'} | "
        f"Turns: {diag['session_turns']}{err_summary}"
    )
    log_step(story_num, "BKM049_DIAGNOSTICS", summary_str, severity="WARNING")
    print(f"\n🩺 {summary_str}", flush=True)
    if diag["session_errors"]:
        print(
            f"   └─ Subagent Internal Errors Detected ({len(diag['session_errors'])}):",
            flush=True,
        )
        for se in diag["session_errors"]:
            print(f"      • {se}", flush=True)
    print(
        "   💡 [PLAYBOOK AUDIT]: Review OPENAGENT_HANDOVER_PLAYBOOK.md to avoid common pitfalls (MCP bloat, agent inversion, root indexing, concurrency deadlocks).",
        flush=True,
    )

    try:
        subprocess.run(
            [
                "icm",
                "store",
                "-t",
                "errors-resolved",
                "-c",
                f"BKM-049 Diagnostics for Story {story_num} (Attempt {attempt}, {reason}): {summary_str}",
                "-i",
                "medium",
                "-k",
                f"bkm049,diagnostics,retry,story-{story_num}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        pass
    return diag


def _verify_and_sync_service_freshness(story_num):
    """[FEAT-553] Verify opencode-core.service PID was started after latest config mtime. Auto-restart if stale."""
    configs = [
        os.path.expanduser("~/Dev_Lab/opencode.json"),
        os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json"),
        os.path.expanduser("~/.config/opencode/oh-my-openagent.json"),
    ]
    existing_configs = [c for c in configs if os.path.exists(c)]
    if not existing_configs:
        return

    try:
        res = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                "opencode-core.service",
                "--property=MainPID",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        pid_str = res.stdout.strip().split("=")[-1]
        if not pid_str or pid_str == "0":
            return
        pid = int(pid_str)
        proc_stat = os.stat(f"/proc/{pid}")
        proc_start_time = proc_stat.st_mtime

        stale_configs = [
            c for c in existing_configs if os.path.getmtime(c) > proc_start_time
        ]
        if stale_configs:
            log_step(
                story_num,
                "STALE_SERVICE_SYNC",
                f"Config modification detected after service start ({', '.join(os.path.basename(c) for c in stale_configs)}). Hot-restarting opencode-core.service...",
            )
            subprocess.run(
                ["systemctl", "--user", "restart", "opencode-core.service"], check=False
            )
            time.sleep(2.0)
    except Exception:
        pass


def _prewarm_target_context(target_files: str | None, story_num: int | str, title: str, details: str):
    """[FEAT-643] Pre-warm semantic context cache in /tmp/clara_context_cache.json via M5 Air Neural Map-Reduce."""
    if not target_files:
        return
    try:
        homelab_src = os.path.expanduser("~/Dev_Lab/HomeLabAI/src")
        if homelab_src not in sys.path:
            sys.path.insert(0, homelab_src)
        from v5.cognition.context_prewarmer import prewarm_files
        files = [f.strip() for f in target_files.split(",") if f.strip()]
        if files:
            prewarm_files(files, max_workers=4)
    except Exception as e:
        sys.stderr.write(f"[*] Pre-warm warning: {e}\n")


def _write_conductor_notes(target_files: str | None, sprint_num: int, story_num: any, title: str):
    """[FEAT-647 / DISC-012] Pre-compute conductor patch notes for $L_3$ JITC grounding.

    Writes AST anchors, diff directives, and story directives to
    /tmp/clara_conductor_notes.json, which the `research` tool (clara_dna_research)
    serves back to workers as "empirical findings" instead of letting them
    unconstrainedly wander the repo.
    """
    if not target_files:
        return
    notes_path = "/tmp/clara_conductor_notes.json"
    notes = {}
    try:
        for path in [f.strip() for f in target_files.split(",") if f.strip()]:
            ast_anchor_lines = []
            try:
                with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
                    src = f.read()
                    for i, line in enumerate(src.splitlines(), 1):
                        if re.match(r"^(def |class |@)", line.strip()):
                            ast_anchor_lines.append(f"L{i}: {line.strip()}")
            except Exception:
                ast_anchor_lines = []
            notes[path] = {
                "sprint": sprint_num,
                "story": str(story_num),
                "story_title": title,
                "notes": f"Conductor directive for Sprint {sprint_num} Story {story_num}: {title}.",
                "ast_anchors": ast_anchor_lines,
                "diff_directives": [f"Apply story {story_num} edits to {path}"],
            }
        with open(notes_path, "w") as f:
            json.dump(notes, f, indent=2)
    except Exception as e:
        sys.stderr.write(f"[*] Conductor cache write failed: {e}\n")


# [FEAT-440] Taxonomy Separation: Agent DNA vs. User Work History
def delegate(
    story_num,
    title,
    reference_file,
    details,
    verification,
    sprint_num=50,
    target_dir=None,
    agent=None,
    max_retries=3,
    mode="execute",
    target_files=None,
    session_id=None,
    sprint_doc=None,
    local_only=True,
    cloud_only=False,
    profile="auto",
):
    """Dispatch a story specification to OpenAgent swarm via REST session attachment with 503 self-healing retry logic."""
    import random
    import threading

    # [Directory Protection Pre-Check]
    # Automatically infer target_dir if omitted, and verify .opencodeignore exists.
    if (
        not target_dir
        or target_dir == DEFAULT_TARGET_DIR
        or target_dir == os.path.expanduser("~")
    ):
        probe = target_files or reference_file or ""
        candidate = None
        for part in probe.replace(",", " ").split():
            clean_part = part.strip()
            if not clean_part:
                continue
            # Try path itself or parent dirs if file does not exist yet
            p_dir = clean_part
            if os.path.exists(clean_part) and not os.path.isdir(clean_part):
                p_dir = os.path.dirname(clean_part)
            elif not os.path.exists(clean_part):
                p_dir = os.path.dirname(clean_part)

            curr = os.path.abspath(p_dir) if p_dir else ""
            while curr and curr != "/" and curr != os.path.expanduser("~"):
                if os.path.exists(
                    os.path.join(curr, ".opencodeignore")
                ) and not os.path.exists(os.path.join(curr, ".gitmodules")):
                    candidate = curr
                    break
                curr = os.path.dirname(curr)
            if candidate:
                break

        if not candidate:
            if "Portfolio_Dev" in probe:
                candidate = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
            else:
                candidate = os.path.expanduser("~/Dev_Lab/HomeLabAI")
        target_dir = candidate

    # Pre-check protection: target_dir must contain .opencodeignore and must not be root monorepo
    if not os.path.exists(os.path.join(target_dir, ".opencodeignore")):
        print(
            f"\n❌ [DELEGATION REJECTED]: Target directory '{target_dir}' is unprotected (missing .opencodeignore).",
            file=sys.stderr,
        )
        print(
            "   Scoping to an unprotected directory risks severe workspace token bloat.",
            file=sys.stderr,
        )
        print(
            "   Specify a valid project directory via --dir or ensure .opencodeignore exists.",
            file=sys.stderr,
        )
        sys.exit(1)

    if os.path.exists(os.path.join(target_dir, ".gitmodules")):
        print(
            f"\n❌ [DELEGATION REJECTED]: Target directory '{target_dir}' is the top-level monorepo root.",
            file=sys.stderr,
        )
        print(
            "   Direct monorepo root indexing is forbidden by playbook (causes multi-repo context explosion).",
            file=sys.stderr,
        )
        print(
            "   Scope delegation to a child submodule directory (e.g. --dir HomeLabAI).",
            file=sys.stderr,
        )
        sys.exit(1)

    # [BKM-049 / BKM-061] Canonical Topology Gate
    if mode == "oracle":
        cloud_only = True
        local_only = False
        agent = "oracle"
    elif mode == "cloud" or cloud_only:
        cloud_only = True
        local_only = False
        if agent and agent not in ("sisyphus", "default"):
            print(
                f"\n❌ [DELEGATION REJECTED]: Agent '{agent}' is invalid for --cloud mode.",
                file=sys.stderr,
            )
            print(
                "   Cloud execution strictly routes to Sisyphus (Executor) or Oracle (Synthesizer).",
                file=sys.stderr,
            )
            print(
                "   See OPENAGENT_HANDOVER_PLAYBOOK.md for topology specifications.",
                file=sys.stderr,
            )
            sys.exit(1)
        agent = agent if agent else "sisyphus"
    elif mode == "local" or local_only:
        local_only = True
        cloud_only = False
        if agent and agent not in (
            "atlas",
            "sisyphus-junior",
            "junior",
            "hephaestus",
            "daedalus",
            "default",
        ):
            print(
                f"\n❌ [DELEGATION REJECTED]: Agent '{agent}' is invalid for --local mode.",
                file=sys.stderr,
            )
            print(
                "   Local execution strictly routes to Atlas (KENDER 4090 Conductor) or Junior (M5 Air Leaf Worker).",
                file=sys.stderr,
            )
            print(
                "   See OPENAGENT_HANDOVER_PLAYBOOK.md for topology specifications.",
                file=sys.stderr,
            )
            sys.exit(1)
        agent = agent if agent else "atlas"
    else:
        agent = agent if agent else "atlas"

    _target_display = target_files if target_files else reference_file
    live_gate_status = "UNSPECIFIED"
    live_gate_details = ""
    log_step(
        story_num,
        "START",
        f"Initiating delegation ({mode.upper()}) for Sprint {sprint_num} '{title}' (agent: {agent}, reference: {reference_file}, target: {_target_display})",
    )

    # 1. Pre-flight quota check & service ignition
    check_cloud_quota()
    _verify_and_sync_service_freshness(story_num)
    _prewarm_target_context(target_files, story_num, title, details)
    _write_conductor_notes(target_files, sprint_num, story_num, title)

    # Auto-start opencode-core.service if inactive (Scale-to-Zero resilience)
    try:
        subprocess.run(
            ["systemctl", "--user", "start", "opencode-core.service"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
    except Exception:
        pass

    # [BKM-049 / Anti-Parallel Execution Gate]
    # Check if any prior session is still actively running in OpenCode.
    # If a live execution is in progress and we are not explicitly attaching via --session-id, REJECT to prevent parallel race conditions.
    if not session_id:
        try:
            status_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/status"
            )
            with urllib.request.urlopen(status_req, timeout=3) as st_resp:
                st_data = json.loads(st_resp.read().decode("utf-8"))
                active_sessions = []
                if isinstance(st_data, dict):
                    active_sessions = [
                        s_id
                        for s_id, s_info in st_data.items()
                        if isinstance(s_info, dict)
                        and s_info.get("status") in ("running", "busy")
                    ]
                elif isinstance(st_data, list):
                    active_sessions = [
                        s.get("id")
                        for s in st_data
                        if isinstance(s, dict)
                        and s.get("status") in ("running", "busy")
                    ]

                if active_sessions:
                    log_step(
                        story_num,
                        "ACTIVE_SESSION_GATE_REJECTED",
                        f"REJECTED: Session {active_sessions[0]} is still actively running. Parallel delegation is strictly forbidden per BKM-049.",
                        severity="CRITICAL",
                    )
                    print(
                        f"\n[!!!] ANTI-PARALLEL GATE TRIGGERED: Session {active_sessions[0]} is still active.",
                        file=sys.stderr,
                    )
                    print(
                        f"[!!!] Wait for it to complete or terminate it before launching Story {story_num}.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        except Exception:
            pass

    session_title = f"Sprint {sprint_num} Story {story_num} (Run {int(time.time())}) — [{mode.upper()}:{agent.upper()}] {title}"

    # Dynamically resolve agent model bindings from oh-my-openagent.json (declarative source of record)
    agent_model_bindings = {}
    omo_config_path = os.path.expanduser("~/.config/opencode/oh-my-openagent.json")
    if os.path.exists(omo_config_path):
        try:
            with open(omo_config_path, "r", encoding="utf-8") as f:
                omo_cfg = json.load(f)
                agents_cfg = omo_cfg.get("agents", {})
                for a_name, a_info in agents_cfg.items():
                    raw_model = a_info.get("model", "")
                    if "/" in raw_model:
                        prov, mod = raw_model.split("/", 1)
                        agent_model_bindings[a_name] = {
                            "providerID": prov,
                            "modelID": mod,
                        }
                if "sisyphus-junior" in agent_model_bindings and "junior" not in agent_model_bindings:
                    agent_model_bindings["junior"] = agent_model_bindings["sisyphus-junior"]
        except Exception:
            pass

    # 2. Attach to existing session or create a fresh session via REST API on port 4097
    active_session_valid = False
    if session_id:
        try:
            check_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}"
            )
            with urllib.request.urlopen(check_req, timeout=3) as c_resp:
                if c_resp.status == 200:
                    active_session_valid = True
                    log_step(
                        story_num,
                        "SESSION_REUSED",
                        f"Reusing verified REST session {session_id}",
                    )
        except Exception:
            active_session_valid = False

    if not active_session_valid:
        # Pre-flight Live MCP Server Probe
        mcp_ok, mcp_msg = _probe_mcp_server()
        if not mcp_ok:
            log_step(
                story_num,
                "MCP_PREFLIGHT_FAILED",
                f"Canonical MCP server probe failed: {mcp_msg}",
                severity="CRITICAL",
            )
            sys.exit(1)
        else:
            log_step(
                story_num,
                "MCP_PREFLIGHT_OK",
                "Canonical MCP server (:stdio) verified live with all mandatory tools",
            )

        try:
            session_payload = {
                "directory": target_dir,
                "title": session_title,
                "agent": agent,
            }
            if agent in agent_model_bindings:
                session_payload["model"] = {
                    "providerID": agent_model_bindings[agent]["providerID"],
                    "id": agent_model_bindings[agent]["modelID"],
                }
            req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session",
                data=json.dumps(session_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                session_id = data["id"]
                log_step(
                    story_num, "SESSION_CREATED", f"Created REST session {session_id}"
                )
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
            log_step(
                story_num,
                "SESSION_FAILED",
                f"Failed to create session via REST on port {OPENCODE_REST_PORT}: {e}",
                severity="CRITICAL",
            )
            sys.exit(1)

    # 3. Poke Web UI (socket activation) AFTER session creation so Web GUI discovers new session
    global _ACTIVE_SESSION_ID
    _ACTIVE_SESSION_ID = session_id
    _register_active_session(session_id, session_title, agent)
    wake_web_ui()
    log_step(
        story_num,
        "WEB_UI_LINK",
        f"Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}",
    )

    # Build dynamic prompt blueprint based on mode
    if mode == "oracle":
        mandate_block = """[LONG-CONTEXT SYNTHESIS & INSIGHT ORACLE DIRECTIVE — READ-ONLY]
You are the Cloud Oracle (Powered by Nemotron-120B / Command-A+ / Groq-70B).
You are strictly an advisory synthesizer. You MUST NOT edit files or emit file edit tool calls.
Your goal is high-level conceptual structuring, thematic clustering, and adversarial review:
  1. THEMATIC CLUSTERING & RECURRING AXIOMS: Group raw notes without altering verbatim origin quotes.
  2. SEQUENCED OUTLINE PROPOSAL: Structured sections with proposed WIS-xxx mappings.
  3. ADVERSARIAL PEER REVIEW: Scrutinize logical gaps, KV/context assumptions, and missing literature.
  4. ACADEMIC TAXONOMY BRIDGES: Map informal engineering idioms to formal literature citations."""
        note_block = "[NOTE] Output the conceptual synthesis / adversarial review report in markdown only. Apply ZERO file edits."
    elif agent == "atlas":
        # Calculate approximate line range in sprint document for Story pointer
        _sprint_line_pointer = ""
        if reference_file and os.path.exists(reference_file):
            try:
                with open(reference_file, "r") as rf:
                    r_lines = rf.readlines()
                    start_idx = None
                    end_idx = None
                    for idx, line in enumerate(r_lines):
                        if f"Story {story_num}" in line:
                            start_idx = idx + 1
                            break
                    if start_idx:
                        # Find next story or end of section
                        for idx in range(start_idx, len(r_lines)):
                            if (
                                "### ⏱️ Story" in r_lines[idx]
                                or "### 🏛️ Architecture" in r_lines[idx]
                            ):
                                end_idx = idx
                                break
                        if not end_idx:
                            end_idx = min(len(r_lines), start_idx + 140)
                        _sprint_line_pointer = f" (Lines {start_idx}–{end_idx})"
            except Exception:
                pass

        _coder_category = "deep" if cloud_only else "quick"
        mandate_block = f"""[STORY {story_num}: {title}]
Sprint Reference: {reference_file}{_sprint_line_pointer}
Edit Target(s): {target_files or reference_file}

[ORCHESTRATION DIRECTIVE]
Operate strictly under AGENTS_L2.md. Ingest Story {story_num}. Use clara-dna_read to inspect file outlines and slice exact line ranges, keeping conductor context pristine (<2,000 tokens). Synthesize a single bounded (<2,000 token) contract for Layer 3 via task(category='{_coder_category}').
If ANY tool in your manifest is unavailable, or contract is under-specified, FAST-HALT IMMEDIATELY ON TURN 1 (<50 tokens) with:
[BLOCKER REPORT: TOOL UNAVAILABLE]
Reason: <tool_name> is unavailable.
Strictly zero internal reasoning monologues once a blocker is detected."""
        note_block = f"[NOTE] Ingest requirements and dispatch a bounded contract to Junior via task(category='{_coder_category}')."
    else:
        mandate_block = f"""[STORY {story_num}: {title}]
The architectural plan for this task is vetted and solid. Do not perform open-ended file searches or re-plan the system. All exact implementation details, AST anchors, and patch blueprints come directly from your JITC research tool. Trust the plan, and verify the live details by running research(target_file) on Turn 1. 1) Review empirical findings from research(). 2) Apply surgical changes via safe_patch(). 3) Run verification (call failure_whisperer(traceback) on failure). 4) Call handoff_checkpoint() on pass.
If ANY mandatory tool is missing or fails, FAST-HALT IMMEDIATELY ON TURN 1 (<50 tokens) with:
[BLOCKER REPORT: TOOL UNAVAILABLE]
Reason: <tool_name> is unavailable.
Strictly zero internal reasoning monologues once a blocker is detected."""
        _edit_scope = target_files if target_files else reference_file
        note_block = f"[NOTE] Apply code modifications strictly to {_edit_scope}."

    # [BKM-034 Two-Tier Payload Construction]
    effective_sprint_doc = sprint_doc or (
        reference_file if reference_file and "SPRINT_PLAN" in reference_file else None
    )
    tier1_block = ""
    if not local_only and effective_sprint_doc:
        sprint_summary = _extract_sprint_summary(effective_sprint_doc)
        if sprint_summary:
            tier1_block = f"""[TIER 1: GLOBAL SPRINT SITUATIONAL AWARENESS]
Sprint Reference: {effective_sprint_doc}
{sprint_summary}

---
"""

    # [FEAT-600 / LAB-019 / FEAT-631] Resident Ambient Memory & Knowledge Recall for OpenAgent Dispatches
    ambient_grounding_block = ""
    try:
        req_payload = json.dumps(
            {
                "prompt": f"{title} {details[:300]}",
                "invocationNum": 1,
                "agent": agent,
            }
        ).encode("utf-8")
        amb_req = urllib.request.Request(
            "http://127.0.0.1:8765/ambient_recall",
            data=req_payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(amb_req, timeout=0.50) as amb_resp:
            amb_data = json.loads(amb_resp.read().decode("utf-8"))
            steps = amb_data.get("injectSteps", [])
            if steps and "ephemeralMessage" in steps[0]:
                ambient_grounding_block = (
                    f"{steps[0]['ephemeralMessage']}\n\n---\n\n"
                )
    except Exception:
        pass

    if local_only and effective_sprint_doc:
        tier1_block = f"""[TIER 1: SPRINT REFERENCE]
Reference File: {effective_sprint_doc}

---
"""

    # Optional target file snippet injection
    target_snippet_block = ""
    if (
        not local_only
        and target_files
        and os.path.exists(target_files.split(",")[0].strip())
    ):
        first_target = target_files.split(",")[0].strip()
        try:
            with open(first_target, "r") as tf:
                lines = tf.readlines()
                snippet = "".join(lines[:80])
                target_snippet_block = f"\n[INCUMBENT TARGET CODE SNIPPET: {first_target}]\n```python\n{snippet}\n```\n"
        except Exception:
            pass

    _handover_block = """[HANDOVER REFLECTION]
In 1-2 brief sentences, state any blocker or ambiguity encountered during execution."""

    raw_rules = _load_agent_rules(agent)
    agent_rules_block = f"\n[OPERATIONAL INVARIANTS & ABORT MANDATES]\n{raw_rules}\n" if raw_rules else ""

    _target_files_line = (
        f"- Edit Target(s): {target_files}"
        if target_files
        else f"- Edit Target(s): {reference_file} (same as reference)"
    )
    if agent == "atlas":
        prompt = f"""[STORY DELEGATION TARGET: STORY {story_num}]
- Title: {title}
- Sprint Reference: {reference_file}
- Edit Target(s): {target_files or reference_file}
- Mode: {mode.upper()}

{agent_rules_block}
{mandate_block}

{details}

{_handover_block}
{note_block}"""
    else:
        prompt = f"""{ambient_grounding_block}{tier1_block}[TIER 2: BOUNDED STORY TARGET SPECIFICATION]
- Sprint Plan Reference: {reference_file}
- Story: {story_num} ({title})
{_target_files_line}
- Delegation Mode: {mode.upper()}

{agent_rules_block}
{mandate_block}

[FUNCTIONAL REQUIREMENTS & 4-ANCHOR SPECIFICATION]
{details}
{target_snippet_block}
{_handover_block}
{note_block}"""

    # =========================================================================
    # [BKM-049 INVARIANT / ANTI-REGRESSION MANDATE]: ZERO INTERNAL RETRIES.
    # delegate.py is strictly a single-shot execution harness.
    # Retries are smart outer-loop operations driven by AGY diagnostics, never
    # blind script-level loops. Zero failover ladders or retry loops permitted.
    # Model routing, fallbacks, and agent defaults are delegated 100% to OpenAgent
    # declarative config (oh-my-openagent.json).
    # =========================================================================

    # [Sprint 76 Action 2] Hard Context Ceiling Gate for Local Silicon (M5 Air 32k with TurboQuant Headroom)
    if local_only:
        est_tokens = len(prompt) // 4
        if est_tokens > 28000:
            log_step(
                story_num,
                "LOCAL_CONTEXT_OVERFLOW",
                f"ABORT: Prompt length ({est_tokens} est. tokens) exceeds sovereign local ceiling of 28,000 tokens. Decompose prompt first.",
            )
            return

    log_step(
        story_num,
        "DISPATCH_SINGLE_SHOT",
        f"Dispatching single-shot prompt to session {session_id} for agent '{agent}' (BKM-049 Pure Single-Shot)",
    )
    start_time = time.time()
    model_str = agent
    msg_dict = {"agent": agent, "parts": [{"type": "text", "text": prompt}]}
    if agent in agent_model_bindings:
        msg_dict["model"] = {
            "providerID": agent_model_bindings[agent]["providerID"],
            "modelID": agent_model_bindings[agent]["modelID"],
        }
        model_str = f"{agent_model_bindings[agent]['providerID']}/{agent_model_bindings[agent]['modelID']}"
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
                poll_req = urllib.request.Request(
                    f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message"
                )
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
                                    q_input = tinput
                                    q_text = ""
                                    q_options = []
                                    if isinstance(q_input, dict):
                                        questions = q_input.get("questions", [])
                                        if isinstance(questions, list) and len(questions) > 0:
                                            q_text = questions[0].get("question", "")
                                            q_options = questions[0].get("options", [])
                                        else:
                                            q_text = q_input.get("question", str(q_input))
                                            q_options = q_input.get("options", [])
                                    else:
                                        q_text = str(q_input)

                                    log_step(
                                        story_num,
                                        "INTERACTIVE_POPUP_DETECTED",
                                        "OpenCode emitted interactive question. Session paused.",
                                        severity="CRITICAL",
                                    )
                                    print("\n" + "=" * 80, flush=True)
                                    print(
                                        f"[INTERACTIVE POPUP — SESSION {session_id}]",
                                        flush=True,
                                    )
                                    print("=" * 80, flush=True)
                                    print(f"QUESTION: {q_text}", flush=True)
                                    if q_options:
                                        print("\nOPTIONS:", flush=True)
                                        for i, opt in enumerate(q_options, 1):
                                            print(f"  [{i}] {opt}", flush=True)
                                    print("\nTo resume, run:", flush=True)
                                    print(
                                        f"  python3 delegate.py --resume {session_id} --answer '<your choice>'",
                                        flush=True,
                                    )
                                    print("=" * 80 + "\n", flush=True)

                                    try:
                                        breadcrumb_path = os.path.expanduser(
                                            "~/Dev_Lab/HomeLabAI/logs/paused_session.txt"
                                        )
                                        os.makedirs(
                                            os.path.dirname(breadcrumb_path),
                                            exist_ok=True,
                                        )
                                        with open(breadcrumb_path, "w") as bf:
                                            bf.write(
                                                f"session_id={session_id}\nstory={story_num}\ntitle={title}\nquestion={q_text}\n"
                                            )
                                    except Exception:
                                        pass

                                    _ACTIVE_SESSION_ID = None
                                    _unregister_active_session()
                                    sys.exit(2)

                                if state_summary != last_inspected_state:
                                    last_inspected_state = state_summary
                                    log_step(
                                        story_num,
                                        "LIVE_SWARM_STATE",
                                        f"State transition: [{state_summary}]",
                                    )
                                break
            except Exception:
                pass

            if post_exception is not None:
                break

            log_step(
                story_num,
                "HEARTBEAT",
                f"OpenAgent execution in progress... ({elapsed}s elapsed). Step log: /tmp/delegate_story_{story_num}.log",
            )

    duration = time.time() - start_time
    tier_str = "[SWARM:LOCAL]" if local_only else ("[SWARM:CLOUD]" if cloud_only else "[SWARM:HYBRID]")

    if post_result is not None:
        api_err = None
        model_obj = post_result.get("info", {}).get("model") if isinstance(post_result, dict) else None
        if not isinstance(model_obj, dict):
            model_obj = {"providerID": agent, "modelID": "openagent"}
        model_str = f"{model_obj.get('providerID', agent)}/{model_obj.get('modelID', 'openagent')}"

        if isinstance(post_result, dict):
            if "error" in post_result.get("info", {}):
                api_err = post_result["info"]["error"]
            elif post_result.get("name") in ("APIError", "UnknownError") or "error" in post_result:
                api_err = post_result.get("data") or post_result.get("error")

        finish = post_result.get("info", {}).get("finish", "unknown") if isinstance(post_result, dict) else "unknown"
        tokens = post_result.get("info", {}).get("tokens", {}) if isinstance(post_result, dict) else {}

        log_step(
            story_num,
            "COMPLETE",
            f"Story {story_num} dispatch ({mode.upper()}) complete in {duration:.1f}s. finish={finish} tokens={tokens}",
        )
        log_step(
            story_num,
            "WEB_UI_LINK",
            f"Direct Web UI Link: http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{session_id}",
        )

        parts = post_result.get("parts", []) if isinstance(post_result, dict) else []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
        full_text = "\n\n".join(t.strip() for t in text_parts if t.strip())

        if api_err and not full_text:
            err_msg = api_err.get("data", {}).get("message") if isinstance(api_err, dict) else str(api_err)
            log_step(story_num, "API_ERROR_DETECTED", f"Provider API Error: {err_msg}", severity="CRITICAL")
            _log_delegation_ledger(
                sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
                session_id, duration, tokens, "API_ERROR", 1, verification, False, str(err_msg)[:200], model_str
            )
            _cleanup_active_session()
            sys.exit(1)

        _log_live_usage_telemetry(
            story_num, sprint_num, title, model_obj, duration, tokens, len(full_text)
        )

        reflection_text = ""
        live_gate_status = "UNSPECIFIED"
        live_gate_details = ""
        if full_text:
            print("\n" + "═" * 80, flush=True)
            print(f"📢 [OPENAGENT EXECUTION REPORT & HANDOVER REFLECTION — STORY {story_num}]", flush=True)
            print("═" * 80, flush=True)
            print(full_text, flush=True)
            print("═" * 80 + "\n", flush=True)

            refl_match = re.search(
                r"(?:\[HANDOVER REFLECTION\]|\*\*Handover Reflection:\*\*)\s*(.+?)(?:\n\n\[|\Z)",
                full_text,
                re.DOTALL | re.IGNORECASE,
            )
            if refl_match:
                reflection_text = refl_match.group(1).strip()
            elif "[HANDOVER REFLECTION]" in full_text:
                reflection_text = full_text.split("[HANDOVER REFLECTION]")[-1].strip()

            # [FEAT-654 Airtight Live Gate Parsing]
            lg_match = re.search(r"\[LIVE_GATE_PENDING:\s*(.+?)\]", full_text, re.IGNORECASE)
            if lg_match:
                live_gate_status = "PENDING"
                live_gate_details = lg_match.group(1).strip()
                print(
                    f"\n╔════════════════════════════════════════════════════════════════════════════╗\n"
                    f"║ ⚠️  [FEAT-654 LIVE GATE PENDING] Layer 1 (AGY) Live Certification Required ║\n"
                    f"╠════════════════════════════════════════════════════════════════════════════╣\n"
                    f"║ Sandbox mocks passed. Live integration must be certified by AGY:           ║\n"
                    f"║ Target: {live_gate_details[:66]:<66} ║\n"
                    f"║ Mandate: Hot-reload daemon (:8765) & test live silicon before Git merge!  ║\n"
                    f"╚════════════════════════════════════════════════════════════════════════════╝\n",
                    flush=True,
                )
            elif "[LIVE_GATE: PASSED]" in full_text.upper():
                live_gate_status = "PASSED"

            blocker_match = re.search(
                r"(?:\[BLOCKER REPORT:\s*(.+?)\]|\*\*Blocker Report:\*\*\s*(.+))",
                full_text,
                re.DOTALL | re.IGNORECASE,
            )
            if blocker_match:
                blocker_text = (blocker_match.group(1) or blocker_match.group(2) or "").strip()
                log_step(story_num, "BLOCKER_DETECTED", f"Subagent emitted blocker report: {blocker_text}", severity="CRITICAL")
                _log_delegation_ledger(
                    sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
                    session_id, duration, tokens, "BLOCKER_HALT", 1, verification, False, blocker_text[:200], model_str,
                    reflection=reflection_text,
                    live_gate_status=live_gate_status,
                    live_gate_details=live_gate_details,
                )
                _cleanup_active_session()
                sys.exit(1)

        if verification and verification != "Post-dispatch AGY Validation":
            log_step(story_num, "VERIFICATION_START", f"Executing single-shot verification: {verification}")
            try:
                monorepo_root = os.path.expanduser("~/Dev_Lab")
                exec_cwd = target_dir if (target_dir and os.path.exists(target_dir)) else (monorepo_root if os.path.exists(monorepo_root) else os.getcwd())
                v_res = subprocess.run(
                    verification,
                    shell=True,
                    cwd=exec_cwd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if v_res.returncode == 0:
                    log_step(story_num, "VERIFICATION_PASSED", f"Verification passed: {verification}")
                    _log_delegation_ledger(
                        sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
                        session_id, duration, tokens, "SUCCESS", 1, verification, True, "", model_str,
                        reflection=reflection_text,
                        live_gate_status=live_gate_status,
                        live_gate_details=live_gate_details,
                    )
                    _trigger_ambient_hook_telemetry(story_num, title, duration, "SUCCESS")
                    _ACTIVE_SESSION_ID = None
                    _unregister_active_session()
                    return
                else:
                    v_output = (v_res.stdout + "\n" + v_res.stderr).strip()
                    log_step(
                        story_num,
                        "VERIFICATION_FAILED",
                        f"Verification failed (code {v_res.returncode}): {v_output[:300]}",
                        severity="CRITICAL",
                    )
                    print(
                        f"❌ [STORY {story_num}] Verification FAILED (code {v_res.returncode}):\n{v_output[:500]}",
                        flush=True,
                    )
                    _log_delegation_ledger(
                        sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
                        session_id, duration, tokens, "VERIFICATION_FAILED", 1, verification, False, v_output[:200], model_str,
                        reflection=reflection_text,
                        live_gate_status=live_gate_status,
                        live_gate_details=live_gate_details,
                    )
                    _trigger_ambient_hook_telemetry(story_num, title, duration, "VERIFICATION_FAILED")
                    _cleanup_active_session()
                    sys.exit(1)
            except subprocess.TimeoutExpired:
                log_step(
                    story_num,
                    "VERIFICATION_TIMEOUT",
                    f"Verification timed out after 120s: {verification}",
                    severity="CRITICAL",
                )
                _log_delegation_ledger(
                    sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
                    session_id, duration, tokens, "VERIFICATION_TIMEOUT", 1, verification, False, "Verification timed out after 120s", model_str,
                    reflection=reflection_text,
                    live_gate_status=live_gate_status,
                    live_gate_details=live_gate_details,
                )
                _trigger_ambient_hook_telemetry(story_num, title, duration, "VERIFICATION_TIMEOUT")
                _cleanup_active_session()
                sys.exit(1)

        _log_delegation_ledger(
            sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
            session_id, duration, tokens, "COMPLETED_UNVERIFIED", 1, verification, None, "", model_str,
            reflection=reflection_text,
            live_gate_status=live_gate_status,
            live_gate_details=live_gate_details,
        )
        _trigger_ambient_hook_telemetry(story_num, title, duration, "COMPLETED_UNVERIFIED")
        _ACTIVE_SESSION_ID = None
        _unregister_active_session()
        return

    if post_exception is not None:
        e = post_exception
        err_ctx = _format_error_context(e)
        log_step(
            story_num,
            "FAILED",
            f"Dispatch failed after {duration:.1f}s: {e}\n{err_ctx}",
            severity="CRITICAL",
        )
        _log_delegation_ledger(
            sprint_num, story_num, title, mode, tier_str, target_files or reference_file,
            session_id, duration, {}, "DISPATCH_FAILED", 1, verification, False, str(e)[:200], model_str,
            live_gate_status=live_gate_status,
            live_gate_details=live_gate_details,
        )
        _cleanup_active_session()
        sys.exit(1)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAgent Swarm Story Delegator")
    parser.add_argument(
        "--retrospective",
        action="store_true",
        help="Synthesize DELEGATION_RETROSPECTIVE.md from /tmp/delegate_story_*.log + REST session metrics, then exit",
    )
    parser.add_argument(
        "--ledger",
        "--show-ledger",
        dest="show_ledger",
        action="store_true",
        help="Display the structured delegation execution ledger table, then exit",
    )
    _retro_mode = "--retrospective" in sys.argv
    _ledger_mode = any(arg in sys.argv for arg in ("--ledger", "--show-ledger"))
    _resume_mode = "--resume" in sys.argv
    _need_story_args = not (_retro_mode or _ledger_mode or _resume_mode)
    parser.add_argument(
        "--sprint", required=_need_story_args, type=int, help="Sprint number"
    )
    parser.add_argument(
        "--story",
        required=_need_story_args,
        type=str,
        help="Story number (e.g. 709, 709B)",
    )
    parser.add_argument("--title", required=_need_story_args, help="Story title")
    parser.add_argument(
        "--reference",
        required=_need_story_args,
        help="Sprint plan / context reference document (read-only context for Atlas)",
    )
    parser.add_argument(
        "--sprint-doc",
        default=None,
        help="Path to Master Sprint Plan (e.g. Portfolio_Dev/SPRINT_PLAN_SPR_65_0.md) to automatically inject Tier-1 Executive Summary",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Actual file(s) Atlas is permitted to edit (omit to default to --reference). Separate multiple paths with commas.",
    )
    parser.add_argument(
        "--details", required=_need_story_args, help="Detailed requirements"
    )
    parser.add_argument(
        "--mode",
        choices=["local", "cloud", "oracle"],
        default="local",
        help="Delegation mode: local (Atlas on sovereign silicon), cloud (Sisyphus on Cloud swarm), or oracle (Cloud Oracle review)",
    )
    parser.add_argument(
        "--local",
        "--local-only",
        dest="force_local",
        action="store_true",
        help="Shorthand for --mode local",
    )
    parser.add_argument(
        "--cloud",
        "--cloud-only",
        dest="force_cloud",
        action="store_true",
        help="Shorthand for --mode cloud",
    )
    parser.add_argument(
        "--oracle",
        dest="force_oracle",
        action="store_true",
        help="Shorthand for --mode oracle",
    )
    parser.add_argument(
        "--verification",
        default="Post-dispatch AGY Validation",
        help="Verification command line (optional)",
    )
    parser.add_argument("--dir", default=None, help="Target working directory")
    parser.add_argument(
        "--retries",
        default=1,
        type=int,
        help="[DEPRECATED]: delegate.py is strictly single-shot per BKM-049.",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Optional explicit agent override (e.g. atlas, sisyphus, junior, oracle)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Existing REST session ID to attach to for context reuse across multi-step iterations",
    )
    parser.add_argument(
        "--resume",
        default=None,
        metavar="SESSION_ID",
        help="Resume a paused interactive session (exit code 2) by sending an answer to the pending question",
    )
    parser.add_argument(
        "--profile",
        default="auto",
        choices=["auto", "builder", "editorial", "research"],
        help="Context profile for contract-driven dynamic pointers (LAB-113): builder, editorial, or research",
    )
    args = parser.parse_args()
    if args.force_oracle:
        args.mode = "oracle"
    elif args.force_cloud:
        args.mode = "cloud"
    elif args.force_local:
        args.mode = "local"

    local_only = args.mode == "local"
    cloud_only = args.mode in ("cloud", "oracle")

    if args.show_ledger:
        show_delegation_ledger(limit=30)
        sys.exit(0)

    # [FEAT-515 / Task 69.6.1] Interactive Session Resume Handler
    if args.resume:
        if not args.answer:
            print(
                "[!] --resume requires --answer <choice> to send a response to the paused session.",
                flush=True,
            )
            sys.exit(1)
        resume_sid = args.resume
        print(
            f"[*] Resuming paused session {resume_sid} with answer: {args.answer}",
            flush=True,
        )
        try:
            resume_payload = json.dumps(
                {"parts": [{"type": "text", "text": args.answer}]}
            ).encode("utf-8")
            resume_req = urllib.request.Request(
                f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{resume_sid}/message",
                data=resume_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(resume_req, timeout=600) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                parts = result.get("parts", [])
                text_parts = [
                    p.get("text", "")
                    for p in parts
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                full_text = "\n\n".join(t.strip() for t in text_parts if t.strip())
                if full_text:
                    print("\n" + "=" * 80, flush=True)
                    print(f"[RESUME RESPONSE — SESSION {resume_sid}]", flush=True)
                    print("=" * 80, flush=True)
                    print(full_text, flush=True)
                    print("=" * 80 + "\n", flush=True)
                else:
                    print(
                        f"[!] Resume completed but no text returned. Check session at http://192.168.1.238:{OPENCODE_WEB_PORT}/#/session/{resume_sid}",
                        flush=True,
                    )
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
        mode=args.mode,
        target_files=args.target,
        session_id=args.session_id,
        sprint_doc=args.sprint_doc,
        local_only=local_only,
        cloud_only=cloud_only,
        profile=args.profile,
    )


def delegate_story(story_num: str | int, resume_session: str | None = None) -> dict:
    """[FEAT-648] Thin wrapper for Story 98.3 session resumption testing.
    
    Args:
        story_num: Story identifier (e.g., "98.2")
        resume_session: Optional session ID to resume
        
    Returns:
        Dict with keys: 'method' (POST/GET), 'url', 'json' (if POST)
    """
    from v5.cognition.context_prewarmer import get_warm_session, register_warm_session
    
    # Try to get warm session for this story
    warm_session = get_warm_session(str(story_num))
    
    if resume_session:
        # Explicit resume requested - use provided session
        session_id = resume_session
        method = "POST"
        url = f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message"
        json_data = {
            "agent": "sisyphus-junior",
            "parts": [{"type": "text", "text": f"Resume story {story_num}"}]
        }
    elif warm_session:
        # Warm session found - reuse it
        session_id = warm_session
        method = "POST"
        url = f"http://127.0.0.1:{OPENCODE_REST_PORT}/session/{session_id}/message"
        json_data = {
            "agent": "sisyphus-junior",
            "parts": [{"type": "text", "text": f"Continue story {story_num}"}]
        }
    else:
        # No warm session - create new one (fallback for test)
        session_id = f"sess-test-{int(time.time())}"
        method = "POST"
        url = f"http://127.0.0.1:{OPENCODE_REST_PORT}/session"
        json_data = {
            "directory": "/tmp",
            "title": f"Test session for story {story_num}",
            "agent": "sisyphus-junior"
        }
        # Register as warm session for future use
        register_warm_session(session_id, str(story_num), "sisyphus-junior")
    
    return {
        "method": method,
        "url": url,
        "json": json_data if method == "POST" else None,
        "session_id": session_id
    }
