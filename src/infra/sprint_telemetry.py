#!/usr/bin/env python3
"""
sprint_telemetry.py — [FEAT-660] Sprint Story Execution & Token Telemetry Tool.

Gathers authoritative execution status, token metrics, cached tokens (KV cache reads),
and wall-clock duration across all stories in a sprint from:
1. OpenCode REST sessions (http://127.0.0.1:4096/session & child subagents).
2. Delegation Ledger (HomeLabAI/data/delegation_ledger.jsonl).
3. Step logs (/tmp/delegate_story_<sprint>.*.log).
"""

import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

OPENCODE_REST_URL = os.environ.get("OPENCODE_REST_URL", "http://127.0.0.1:4096/session")
HOMELAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER_PATH = os.path.join(HOMELAB_DIR, "data", "delegation_ledger.jsonl")


def fetch_rest_sessions() -> List[Dict[str, Any]]:
    """Fetch all active and completed sessions from OpenCode REST API."""
    try:
        req = urllib.request.Request(OPENCODE_REST_URL)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []
    except Exception:
        return []


def get_sprint_metrics(sprint: int = 101) -> Dict[str, Any]:
    """Compile comprehensive execution metrics for a sprint."""
    sessions = fetch_rest_sessions()
    prefix = f"{sprint}."

    # Index REST sessions
    story_parents: Dict[str, List[Dict[str, Any]]] = {}
    children_by_parent: Dict[str, List[Dict[str, Any]]] = {}

    for s in sessions:
        pid = s.get("parentID")
        if pid:
            children_by_parent.setdefault(pid, []).append(s)

        title = s.get("title", "")
        m = re.search(r"Story\s*(" + re.escape(str(sprint)) + r"\.\d+[A-Z]?)", title, re.IGNORECASE)
        if m:
            st_id = m.group(1)
            story_parents.setdefault(st_id, []).append(s)

    # Read delegation ledger
    ledger_records: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if str(item.get("sprint")) == str(sprint):
                        st = str(item.get("story"))
                        if not st.startswith(prefix):
                            st = f"{sprint}.{st}"
                        # Keep latest record for the story
                        ledger_records[st] = item
        except Exception:
            pass

    # Read step logs from /tmp
    log_records: Dict[str, Dict[str, Any]] = {}
    log_pattern = f"/tmp/delegate_story_{sprint}.*.log"
    for log_file in sorted(glob.glob(log_pattern)):
        m = re.search(r"delegate_story_(" + re.escape(str(sprint)) + r"\.\d+[A-Z]?)\.log", log_file)
        if not m:
            continue
        st = m.group(1)
        try:
            with open(log_file, "r", encoding="utf-8") as lf:
                content = lf.read()
            duration = 0.0
            status = "UNKNOWN"
            comp_matches = re.findall(r"\[COMPLETE\]\s*Story.*?complete in ([\d\.]+)s", content)
            if comp_matches:
                duration = float(comp_matches[-1])
                status = "COMPLETED"
            if "VERIFICATION_PASSED" in content:
                status = "VERIFIED"
            elif "VERIFICATION_FAILED" in content:
                status = "FAILED"
            log_records[st] = {"duration_s": duration, "status": status}
        except Exception:
            pass

    # Discover all story keys
    all_story_keys = sorted(
        list(set(list(story_parents.keys()) + list(ledger_records.keys()) + list(log_records.keys()))),
        key=lambda k: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", k)],
    )

    stories_data = []
    total_in = 0
    total_out = 0
    total_cache = 0
    total_tokens = 0
    total_l3_sub = 0
    total_duration_s = 0.0
    completed_count = 0

    for st in all_story_keys:
        # Aggregate REST tokens
        st_sessions = story_parents.get(st, [])
        all_family = []
        for p in st_sessions:
            all_family.append(p)
            for c in children_by_parent.get(p.get("id"), []):
                all_family.append(c)

        rest_in = sum(s.get("tokens", {}).get("input", 0) for s in all_family)
        rest_out = sum(s.get("tokens", {}).get("output", 0) for s in all_family)
        rest_cache = sum(s.get("tokens", {}).get("cache", {}).get("read", 0) for s in all_family)
        rest_total = sum(s.get("tokens", {}).get("total", 0) for s in all_family)

        # Ledger data
        led = ledger_records.get(st, {})
        led_tok = led.get("tokens", {}) if isinstance(led.get("tokens"), dict) else {}
        led_in = led_tok.get("input", 0)
        led_out = led_tok.get("output", 0)
        led_cache = led_tok.get("cache", {}).get("read", 0) if isinstance(led_tok.get("cache"), dict) else 0
        led_total = led_tok.get("total", 0)
        led_duration = float(led.get("duration_s", 0.0))

        sub_inf = led_tok.get("sub_inference", {}) if isinstance(led_tok.get("sub_inference"), dict) else {}
        l3_sub_tokens = sub_inf.get("total_tokens", 0)

        # Best metrics resolution
        inp = max(rest_in, led_in)
        out = max(rest_out, led_out)
        cache = max(rest_cache, led_cache)
        cond_tot = max(rest_total, led_total, inp + out)
        blended_tot = cond_tot + l3_sub_tokens

        log_data = log_records.get(st, {})
        dur_s = max(led_duration, log_data.get("duration_s", 0.0))
        dur_m = round(dur_s / 60.0, 2)

        # Status resolution
        status = "PENDING"
        if led.get("status") == "SUCCESS" or log_data.get("status") == "VERIFIED":
            status = "VERIFIED"
            completed_count += 1
        elif log_data.get("status") == "COMPLETED" or led.get("status") in ("COMPLETED_UNVERIFIED", "SUCCESS"):
            status = "COMPLETED"
            completed_count += 1
        elif log_data.get("status") == "FAILED":
            status = "FAILED"
        elif st in story_parents:
            status = "IN_PROGRESS"

        title = led.get("title") or (st_sessions[0].get("title", "") if st_sessions else "")
        mode = led.get("mode") or ("local" if "LOCAL" in title else ("cloud" if "CLOUD" in title else "oracle"))

        stories_data.append({
            "story": st,
            "title": title,
            "mode": mode,
            "status": status,
            "tokens_input": inp,
            "tokens_output": out,
            "tokens_cached": cache,
            "tokens_conductor": cond_tot,
            "tokens_l3_sub": l3_sub_tokens,
            "tokens_total": blended_tot,
            "duration_minutes": dur_m,
        })

        total_in += inp
        total_out += out
        total_cache += cache
        total_tokens += blended_tot
        total_l3_sub += l3_sub_tokens
        total_duration_s += dur_s

    return {
        "sprint": sprint,
        "total_stories": len(stories_data),
        "completed_stories": completed_count,
        "stories": stories_data,
        "totals": {
            "tokens_input": total_in,
            "tokens_output": total_out,
            "tokens_cached": total_cache,
            "tokens_conductor": total_tokens - total_l3_sub,
            "tokens_l3_sub": total_l3_sub,
            "tokens_total": total_tokens,
            "wall_time_minutes": round(total_duration_s / 60.0, 2),
        },
    }


def format_markdown_table(data: Dict[str, Any]) -> str:
    """Format metrics into a clean markdown table."""
    sprint = data.get("sprint", 101)
    stories = data.get("stories", [])
    totals = data.get("totals", {})

    lines = [
        f"### 📊 Sprint {sprint} Telemetry Report",
        "",
        "| Story | Status | Mode | Tokens | Cached | Wall Time (min) |",
        "|---|:---:|:---:|:---:|:---:|:---:|",
    ]

    for s in stories:
        st_id = s["story"]
        status = s["status"]
        status_badge = "✅ PASS" if status == "VERIFIED" else ("🟦 DONE" if status == "COMPLETED" else ("🔄 RUN" if status == "IN_PROGRESS" else "❌ FAIL"))
        mode = s["mode"].upper()
        tot = f"{s['tokens_total']:,}"
        cache = f"{s['tokens_cached']:,}"
        dur = f"{s['duration_minutes']:.2f}m"

        lines.append(f"| **{st_id}** | {status_badge} | `{mode}` | {tot} | {cache} | {dur} |")

    lines.append("|---|:---:|:---:|:---:|:---:|:---:|")
    t_tot = f"**{totals.get('tokens_total', 0):,}**"
    t_cache = f"**{totals.get('tokens_cached', 0):,}**"
    t_dur = f"**{totals.get('wall_time_minutes', 0.0):.2f}m**"
    lines.append(f"| **TOTALS** | **{data.get('completed_stories', 0)}/{data.get('total_stories', 0)}** | — | {t_tot} | {t_cache} | {t_dur} |")
    lines.append("")

    return "\n".join(lines)


def export_web_telemetry(output_path: Optional[str] = None) -> Dict[str, Any]:
    """[Story 101.14] Export full delegation ledger (sprints 78-101) as a web feed JSON."""
    if output_path is None:
        output_path = os.path.join("..", "Portfolio_Dev", "field_notes", "data", "delegation_runs.json")

    success_statuses = {"SUCCESS", "COMPLETED_UNVERIFIED", "completed", "COMPLETED"}
    runs: List[Dict[str, Any]] = []

    total_input = 0
    total_output = 0
    total_cached = 0
    total_conductor = 0
    total_l3 = 0
    total_blended = 0
    total_wall_minutes = 0.0
    successful_runs = 0

    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue

                status = str(item.get("status", ""))
                if status in success_statuses:
                    successful_runs += 1

                tok = item.get("tokens", {}) if isinstance(item.get("tokens"), dict) else {}
                sub_inf = tok.get("sub_inference", {}) if isinstance(tok.get("sub_inference"), dict) else {}

                inp = tok.get("input", 0)
                out = tok.get("output", 0)
                cache = tok.get("cache", {}).get("read", 0) if isinstance(tok.get("cache"), dict) else 0
                l3_tokens = sub_inf.get("total_tokens", 0)
                conductor = tok.get("total", 0) or (inp + out)
                blended = (tok.get("total", 0) or (inp + out)) + l3_tokens

                total_input += inp
                total_output += out
                total_cached += cache
                total_conductor += conductor
                total_l3 += l3_tokens
                total_blended += blended

                duration_s = float(item.get("duration_s", 0.0))
                duration_m = round(duration_s / 60.0, 2)
                total_wall_minutes += duration_m

                runs.append({
                    "sprint": str(item.get("sprint", "")),
                    "story": str(item.get("story", "")),
                    "title": item.get("title", ""),
                    "mode": item.get("mode", ""),
                    "tier": item.get("tier", ""),
                    "model": item.get("model", ""),
                    "status": status,
                    "duration_s": duration_s,
                    "duration_m": duration_m,
                    "tokens": {
                        "conductor": conductor,
                        "l3": l3_tokens,
                        "total": blended,
                        "cache_read": cache,
                    },
                    "verification_passed": status == "SUCCESS",
                    "reflection": item.get("summary", ""),
                    "timestamp": item.get("timestamp", ""),
                })

    runs.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

    cloud_cost_usd = (total_input / 1e6 * 3.0) + (total_output / 1e6 * 15.0)
    local_power_cost_usd = 0.2 * (total_wall_minutes / 60.0) * 0.15
    denom = cloud_cost_usd + local_power_cost_usd
    net_savings_usd = cloud_cost_usd - local_power_cost_usd
    local_offload_ratio_pct = (local_power_cost_usd / denom * 100.0) if denom else 0.0

    summary = {
        "total_runs": len(runs),
        "successful_runs": successful_runs,
        "total_tokens_blended": total_blended,
        "total_conductor_tokens": total_conductor,
        "total_l3_tokens": total_l3,
        "total_cached_tokens": total_cached,
        "total_wall_time_minutes": round(total_wall_minutes, 2),
        "estimated_cloud_cost_usd": round(cloud_cost_usd, 6),
        "estimated_local_power_cost_usd": round(local_power_cost_usd, 6),
        "net_savings_usd": round(net_savings_usd, 6),
        "local_offload_ratio_pct": round(local_offload_ratio_pct, 2),
    }

    payload = {"summary": summary, "runs": runs}

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def main():
    parser = argparse.ArgumentParser(description="Sprint Telemetry & Token Metrics Tool")
    parser.add_argument("--sprint", type=int, default=101, help="Sprint number (default: 101)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--export-web", action="store_true", help="Export web feed JSON (full delegation ledger)")
    args = parser.parse_args()

    if args.export_web:
        payload = export_web_telemetry()
        print(f"[OK] Web telemetry feed exported: {LEDGER_PATH} -> ../Portfolio_Dev/field_notes/data/delegation_runs.json")
        print(f"     runs={payload['summary']['total_runs']} successful={payload['summary']['successful_runs']}")
        sys.exit(0)

    data = get_sprint_metrics(args.sprint)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_markdown_table(data))


if __name__ == "__main__":
    main()
