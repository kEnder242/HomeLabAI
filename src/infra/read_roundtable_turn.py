#!/usr/bin/env python3
"""
read_roundtable_turn.py — Fast Round Table Dialogue & Telemetry Extractor
[FEAT-607] High-Speed Turn & Dialogue Extraction for Sovereign Lab Deliberations.

Usage:
  python3 read_roundtable_turn.py [--latest] [--request-id <id>] [--limit 5]
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOMELAB_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
WORKSPACE_DIR = os.path.abspath(os.path.join(HOMELAB_DIR, ".."))
STAGE_LEDGER_PATH = os.path.join(
    WORKSPACE_DIR, "Portfolio_Dev/field_notes/data/foyer_stage_ledger.jsonl"
)
LOGS_DIR = os.path.join(HOMELAB_DIR, "logs")

TRACE_FILES = {
    "stage1_deep_thought_triage": os.path.join(LOGS_DIR, "trace_thought.json"),
    "stage1_kender_triage": os.path.join(LOGS_DIR, "trace_lab.json"),
    "stage2_pinky_hyde": os.path.join(LOGS_DIR, "trace_pinky.json"),
    "stage3_brain_query": os.path.join(LOGS_DIR, "trace_brain.json"),
    "stage4_dt_synthesis": os.path.join(LOGS_DIR, "trace_thought.json"),
    "stage5_pinky_review": os.path.join(LOGS_DIR, "trace_pinky.json"),
}


def parse_recent_ledger_requests(limit: int = 10) -> List[Dict]:
    """Extract recent unique request IDs and their stage entries from the ledger."""
    if not os.path.exists(STAGE_LEDGER_PATH):
        return []

    entries_by_req = {}
    with open(STAGE_LEDGER_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                req_id = data.get("request_id")
                if not req_id:
                    continue
                if req_id not in entries_by_req:
                    entries_by_req[req_id] = []
                entries_by_req[req_id].append(data)
            except Exception:
                continue

    req_keys = list(entries_by_req.keys())
    selected_keys = req_keys[-limit:]
    results = []
    for k in selected_keys:
        stages = entries_by_req[k]
        start_ts = stages[0].get("ts", 0) if stages else 0
        end_ts = stages[-1].get("ts", 0) if stages else 0
        results.append(
            {
                "request_id": k,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "stage_count": len(stages),
                "stages": stages,
            }
        )
    return results


def tail_extract_json_stream(
    file_path: str, max_bytes: int = 2 * 1024 * 1024
) -> List[Tuple[float, str]]:
    """Efficiently extracts recent 'recv' phase data payloads from a large stream JSON file."""
    if not os.path.exists(file_path):
        return []

    try:
        file_size = os.path.getsize(file_path)
        read_size = min(file_size, max_bytes)
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            chunk = f.read()

        recv_blocks = chunk.split('{\n  "phase": "recv"')
        extracted = []
        for b in recv_blocks:
            if not b.strip():
                continue
            full_b = b if b.strip().startswith("{") else '{\n  "phase": "recv"' + b
            m_data = re.search(
                r'"data":\s*"(.*?)(?=",\s*"metadata|\"$)', full_b, re.DOTALL
            )
            m_ts = re.search(r'"timestamp":\s*([\d\.]+)', full_b)
            ts = float(m_ts.group(1)) if m_ts else 0.0
            if m_data:
                try:
                    payload = json.loads('"' + m_data.group(1) + '"')
                    extracted.append((ts, payload))
                except Exception:
                    extracted.append((ts, m_data.group(1)))
        return extracted
    except Exception as e:
        return []


def print_request_detail(req_info: Dict):
    """Pretty prints the stages and extracts corresponding conversation turns."""
    req_id = req_info["request_id"]
    stages = req_info["stages"]
    print(f"\n{'='*75}")
    print(
        f"🔍 REQUEST ID: {req_id} | Stages: {len(stages)} | Duration: {req_info['end_ts'] - req_info['start_ts']:.2f}s"
    )
    print(f"{'='*75}")

    for idx, stg in enumerate(stages, 1):
        stage_name = stg.get("stage", "unknown")
        node_name = stg.get("node", "unknown")
        status = stg.get("status", "unknown")
        log_target = stg.get("log_target", TRACE_FILES.get(stage_name, "N/A"))
        detail = stg.get("detail", "")
        ts = stg.get("ts", 0.0)

        print(f"\n[{idx}] Stage: {stage_name} ({node_name})")
        print(f"    • Status: {status} | Target: {log_target} | ts: {ts:.3f}")
        if detail:
            print(f"    • Detail: {detail}")

        # Attempt extraction from log target if within temporal window
        target_path = (
            os.path.join(HOMELAB_DIR, log_target)
            if not os.path.isabs(log_target)
            else log_target
        )
        if os.path.exists(target_path):
            entries = tail_extract_json_stream(target_path, max_bytes=1024 * 1024)
            # Match entry within +/- 15s window of ledger event ts
            matched = [e for e in entries if abs(e[0] - ts) <= 15.0]
            if matched:
                best_ts, best_payload = matched[-1]
                print(f"    💬 Wire Payload (ts={best_ts:.2f}):")
                indented = "\n".join(f"       {line}" for line in best_payload.splitlines())
                print(indented)


def main():
    parser = argparse.ArgumentParser(
        description="Fast Round Table Dialogue & Telemetry Extractor"
    )
    parser.add_argument(
        "--request-id", "-r", type=str, help="Specific request ID to inspect"
    )
    parser.add_argument(
        "--latest",
        "-l",
        action="store_true",
        help="Inspect the most recent request from the ledger",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=5,
        help="Number of recent requests to list (default: 5)",
    )
    args = parser.parse_args()

    requests = parse_recent_ledger_requests(limit=max(args.limit, 10))
    if not requests:
        print("No stage ledger entries found.")
        sys.exit(0)

    if args.request_id:
        matched = [r for r in requests if r["request_id"] == args.request_id]
        if not matched:
            print(f"Request ID '{args.request_id}' not found in recent ledger entries.")
            sys.exit(1)
        print_request_detail(matched[0])
        return

    if args.latest:
        print_request_detail(requests[-1])
        return

    print("\n--- Recent Round Table Deliberation Sessions ---")
    for r in requests[-args.limit :]:
        print(
            f"• Request ID: {r['request_id']:<10} | Stages: {r['stage_count']:<2} | "
            f"Time: {r['end_ts'] - r['start_ts']:>6.2f}s"
        )
    print("\nUse --latest or --request-id <id> to view full dialogues.")


if __name__ == "__main__":
    main()
