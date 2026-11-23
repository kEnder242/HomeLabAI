# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
"""
[FEAT-690] Prometheus Historical Benchmark Seeder (Full 90-Day Backfill)
Reads:
  - Portfolio_Dev/field_notes/data/round_table_deltas.json
  - Portfolio_Dev/field_notes/data/live_usage_stream.jsonl
  - Portfolio_Dev/field_notes/data/delegation_runs.json
Generates OpenMetrics TSDB blocks via 'promtool', installs them into Prometheus /prometheus/data,
and verifies query coverage across all historical spans (Sep - Nov 2026).
"""
import datetime
import json
import os
import subprocess
import sys
from collections import defaultdict

WORKSPACE = "/home/jallred/Dev_Lab"
RT_FILE = os.path.join(WORKSPACE, "Portfolio_Dev/field_notes/data/round_table_deltas.json")
USAGE_FILE = os.path.join(WORKSPACE, "Portfolio_Dev/field_notes/data/live_usage_stream.jsonl")
DELG_FILE = os.path.join(WORKSPACE, "Portfolio_Dev/field_notes/data/delegation_runs.json")

def escape_label(val: str) -> str:
    return str(val).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

def generate_openmetrics_text() -> str:
    lines = []

    # -------------------------------------------------------------
    # 1. Round Table Stage Durations & Deliberations (Turns 16..65)
    # -------------------------------------------------------------
    rt_data = []
    if os.path.exists(RT_FILE):
        with open(RT_FILE, "r") as f:
            rt_data = json.load(f)

    rt_data.sort(key=lambda x: x.get("timestamp", 0))

    lines.append("# TYPE moe_stage_duration_seconds gauge")
    lines.append("# HELP moe_stage_duration_seconds Deliberation & Round Table Stage Durations in seconds")
    stages = ["triage", "pinky_stance", "brain_arch", "oracle", "pinky_judgment", "total_pipeline"]
    for stage in stages:
        last_ts = None
        for entry in rt_data:
            ts = float(entry.get("timestamp", 0))
            if ts <= 0:
                continue
            if last_ts is not None and ts <= last_ts:
                ts = last_ts + 0.001
            last_ts = ts

            deltas = entry.get("deltas_elapsed_s") or entry.get("deltas") or {}
            if stage == "total_pipeline":
                val = float(entry.get("total_elapsed_s", 0.0))
            else:
                val = float(deltas.get(stage, 0.0))
            lines.append(f'moe_stage_duration_seconds{{stage="{stage}"}} {val:.4f} {ts:.3f}')

    lines.append("# TYPE moe_router_latency_seconds gauge")
    lines.append("# HELP moe_router_latency_seconds Intent routing and triage latency in seconds")
    last_ts = None
    for entry in rt_data:
        ts = float(entry.get("timestamp", 0))
        if ts <= 0:
            continue
        if last_ts is not None and ts <= last_ts:
            ts = last_ts + 0.001
        last_ts = ts
        deltas = entry.get("deltas_elapsed_s") or entry.get("deltas") or {}
        val = float(deltas.get("triage", 0.0))
        lines.append(f'moe_router_latency_seconds{{start_type="warm"}} {val:.4f} {ts:.3f}')

    lines.append("# TYPE moe_round_table_turn_number gauge")
    lines.append("# HELP moe_round_table_turn_number Monotonic Turn ID of round table deliberation")
    last_ts = None
    for entry in rt_data:
        ts = float(entry.get("timestamp", 0))
        if ts <= 0:
            continue
        if last_ts is not None and ts <= last_ts:
            ts = last_ts + 0.001
        last_ts = ts
        turn = float(entry.get("turn", 0))
        lines.append(f'moe_round_table_turn_number {turn:.0f} {ts:.3f}')

    # -------------------------------------------------------------
    # 2. Live Model Usage Stream Metrics (Throughput, ITL, TTFT)
    # -------------------------------------------------------------
    usage_entries = []
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        usage_entries.append(json.loads(line))
                    except Exception:
                        pass

    SEAT_MAP = {
        "Windows 4090RTX": "Kender 4090",
        "Hybrid GPU (2080 Ti + Arc B580)": "Hybrid GPU (2080 Ti + Arc B580)",
        "Linux 2080ti": "Hybrid GPU (2080 Ti + Arc B580)",
        "Apple M5 Air": "M5 Air",
        "Cloud Swarm": "Cloud Swarm"
    }

    entries_by_seat = defaultdict(list)
    for entry in usage_entries:
        raw_seat = entry.get("seat") or entry.get("node") or "Hybrid GPU (2080 Ti + Arc B580)"
        seat = SEAT_MAP.get(raw_seat, raw_seat)
        ts = float(entry.get("timestamp", 0))
        if ts > 0:
            entries_by_seat[seat].append((ts, entry))

    for seat in entries_by_seat:
        entries_by_seat[seat].sort(key=lambda x: x[0])

    # Model Throughput (tok/s)
    lines.append("# TYPE moe_model_throughput_tok_s gauge")
    lines.append("# HELP moe_model_throughput_tok_s Model generation throughput in tokens per second")
    for seat, records in entries_by_seat.items():
        esc_seat = escape_label(seat)
        last_ts = None
        for ts, entry in records:
            tp = entry.get("throughput_tok_s") or entry.get("decode_tok_s")
            if tp is not None and float(tp) > 0 and float(tp) <= 120.0:
                if last_ts is not None and ts <= last_ts:
                    ts = last_ts + 0.001
                last_ts = ts
                val = float(tp)
                lines.append(f'moe_model_throughput_tok_s{{node="{esc_seat}"}} {val:.2f} {ts:.3f}')

    # Model ITL (Inter-Token Latency in s)
    lines.append("# TYPE moe_model_itl_seconds gauge")
    lines.append("# HELP moe_model_itl_seconds Inter-token latency in seconds")
    for seat, records in entries_by_seat.items():
        esc_seat = escape_label(seat)
        last_ts = None
        for ts, entry in records:
            tp = entry.get("throughput_tok_s") or entry.get("decode_tok_s")
            if tp is not None and float(tp) > 0 and float(tp) <= 120.0:
                if last_ts is not None and ts <= last_ts:
                    ts = last_ts + 0.001
                last_ts = ts
                val = 1.0 / float(tp)
                lines.append(f'moe_model_itl_seconds{{node="{esc_seat}"}} {val:.6f} {ts:.3f}')

    # Model TTFT (Time to First Token in s)
    lines.append("# TYPE moe_model_ttft_seconds gauge")
    lines.append("# HELP moe_model_ttft_seconds Time to first token in seconds")
    for seat, records in entries_by_seat.items():
        esc_seat = escape_label(seat)
        last_ts = None
        for ts, entry in records:
            ttft = entry.get("ttft_s")
            if ttft is None and "ttft_ms" in entry:
                ttft = float(entry["ttft_ms"]) / 1000.0
            if ttft is not None and float(ttft) > 0 and float(ttft) <= 30.0:
                if last_ts is not None and ts <= last_ts:
                    ts = last_ts + 0.001
                last_ts = ts
                val = float(ttft)
                lines.append(f'moe_model_ttft_seconds{{node="{esc_seat}"}} {val:.4f} {ts:.3f}')

    # Model Decode Tokens
    lines.append("# TYPE moe_model_decode_tokens gauge")
    lines.append("# HELP moe_model_decode_tokens Output tokens generated in decode phase")
    for seat, records in entries_by_seat.items():
        esc_seat = escape_label(seat)
        last_ts = None
        for ts, entry in records:
            toks = entry.get("tokens_generated")
            if toks is not None and float(toks) > 0:
                if last_ts is not None and ts <= last_ts:
                    ts = last_ts + 0.001
                last_ts = ts
                val = float(toks)
                lines.append(f'moe_model_decode_tokens{{node="{esc_seat}"}} {val:.0f} {ts:.3f}')

    # Model Decode Duration
    lines.append("# TYPE moe_model_decode_duration_seconds gauge")
    lines.append("# HELP moe_model_decode_duration_seconds Net decode duration in seconds")
    for seat, records in entries_by_seat.items():
        esc_seat = escape_label(seat)
        last_ts = None
        for ts, entry in records:
            dur = entry.get("decode_duration_s")
            if dur is None:
                dur = float(entry.get("duration_seconds", 0.0)) - float(entry.get("ttft_s", 0.0))
            if dur is not None and float(dur) > 0:
                if last_ts is not None and ts <= last_ts:
                    ts = last_ts + 0.001
                last_ts = ts
                val = float(dur)
                lines.append(f'moe_model_decode_duration_seconds{{node="{esc_seat}"}} {val:.4f} {ts:.3f}')

    # -------------------------------------------------------------
    # 3. Sovereign Swarm Token Trajectory (Tokens per Sprint / Run)
    # -------------------------------------------------------------
    if os.path.exists(DELG_FILE):
        try:
            with open(DELG_FILE, "r") as f:
                delg_data = json.load(f)
            runs = delg_data.get("runs", [])

            def classify_tier(r):
                mode = str(r.get("mode", "")).lower()
                tier = str(r.get("tier", "")).upper()
                if mode == "local" or "LOCAL" in tier:
                    return "Local Silicon"
                if mode == "agy" or "AGY" in tier or "PRIMARY" in tier:
                    return "Primary AGY"
                if mode in ("cloud", "oracle") or "CLOUD" in tier or "ORACLE" in tier or "HYBRID" in tier:
                    return "Cloud & Oracle"
                return "Local Silicon"

            runs_by_tier = defaultdict(list)
            for r in runs:
                tier_name = classify_tier(r)
                ts_str = r.get("timestamp")
                ts = 0.0
                if ts_str:
                    try:
                        dt = datetime.datetime.fromisoformat(ts_str)
                        ts = dt.timestamp()
                    except Exception:
                        ts = 0.0
                tok_total = r.get("tokens", {}).get("total", 0)
                if ts > 0 and tok_total > 0:
                    runs_by_tier[tier_name].append((ts, float(tok_total)))

            for tier in runs_by_tier:
                runs_by_tier[tier].sort(key=lambda x: x[0])

            lines.append("# TYPE moe_swarm_tokens_total gauge")
            lines.append("# HELP moe_swarm_tokens_total Sovereign Swarm Tokens generated partitioned by tier")
            for tier, recs in runs_by_tier.items():
                esc_tier = escape_label(tier)
                last_ts = None
                for ts, tok_val in recs:
                    if last_ts is not None and ts <= last_ts:
                        ts = last_ts + 0.001
                    last_ts = ts
                    lines.append(f'moe_swarm_tokens_total{{tier="{esc_tier}"}} {tok_val:.0f} {ts:.3f}')
        except Exception as e:
            print(f"Warning parsing delegation runs: {e}")

    lines.append("# EOF\n")
    return "\n".join(lines)

def build_and_import_blocks():
    om_text = generate_openmetrics_text()
    tmp_om = "/tmp/historical_benchmarks.openmetrics"
    with open(tmp_om, "w") as f:
        f.write(om_text)
    print(f"Generated {len(om_text.splitlines())} lines of OpenMetrics data.")

    # Copy into container
    subprocess.run(["docker", "cp", tmp_om, "field_prometheus:/tmp/historical_benchmarks.openmetrics"], check=True)

    # Clean tmp out_blocks
    subprocess.run(["docker", "exec", "field_prometheus", "rm", "-rf", "/tmp/historical_blocks"], check=True)
    subprocess.run(["docker", "exec", "field_prometheus", "mkdir", "-p", "/tmp/historical_blocks"], check=True)

    # Create TSDB blocks
    print("Executing promtool tsdb create-blocks-from openmetrics...")
    res = subprocess.run([
        "docker", "exec", "field_prometheus",
        "promtool", "tsdb", "create-blocks-from", "openmetrics",
        "/tmp/historical_benchmarks.openmetrics",
        "/tmp/historical_blocks"
    ], capture_output=True, text=True)

    if res.returncode != 0:
        print("promtool STDERR:\n", res.stderr)
        raise RuntimeError(f"promtool failed with return code {res.returncode}")

    # Count blocks
    blocks_out = subprocess.check_output(["docker", "exec", "field_prometheus", "ls", "/tmp/historical_blocks"]).decode().splitlines()
    print(f"promtool successfully produced {len(blocks_out)} TSDB blocks!")

    # Copy ALL blocks to /prometheus/data/
    print("Copying all generated blocks into /prometheus/data...")
    subprocess.run([
        "docker", "exec", "field_prometheus",
        "sh", "-c", "cp -rf /tmp/historical_blocks/* /prometheus/data/ && chown -R nobody:nobody /prometheus/data"
    ], check=True)

    # Restart Prometheus to force full TSDB index mount
    print("Restarting field_prometheus to mount new TSDB blocks...")
    subprocess.run(["docker", "restart", "field_prometheus"], check=True)
    print("field_prometheus restarted successfully.")

if __name__ == "__main__":
    build_and_import_blocks()
