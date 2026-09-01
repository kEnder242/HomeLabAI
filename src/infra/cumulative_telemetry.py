import os
import json
import time

DATA_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
CUMULATIVE_JSON_PATH = os.path.join(DATA_DIR, "cumulative_tokens.json")
STREAM_JSONL_PATH = os.path.join(DATA_DIR, "live_usage_stream.jsonl")

# Standard commercial rate ($3.00 per 1M tokens / Claude 3.5 Sonnet) & residential electricity ($0.15 / kWh)
COMMERCIAL_RATE_PER_1M = 3.00
ELECTRICITY_RATE_PER_KWH = 0.15

# Seat power profiles in Watts
POWER_PROFILES_WATTS = {
    "Apple M5 Air": 18.0,
    "Windows 4090RTX": 290.0,
    "Linux 2080ti": 85.0,
    "Cloud Swarm": 0.0
}


def log_telemetry_event(source: str, task_title: str, seat: str, provider: str, model: str, tokens_generated: int, duration_seconds: float, raw_throughput_tok_s: float = None):
    """
    [FEAT-498] Unified Telemetry Logger:
    1. Appends real-world workload events to live_usage_stream.jsonl
    2. Updates lifetime cumulative sovereign token counters & realized ROI in cumulative_tokens.json
    """
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tokens_generated = int(tokens_generated) if tokens_generated else 0
        duration_seconds = max(0.01, float(duration_seconds)) if duration_seconds else 0.01

        # Effective workflow velocity
        workflow_velocity = round(tokens_generated / duration_seconds, 2)
        tp = round(raw_throughput_tok_s, 2) if raw_throughput_tok_s and raw_throughput_tok_s > 0 else workflow_velocity

        # 1. Append to live_usage_stream.jsonl
        record = {
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "task_title": task_title,
            "seat": seat,
            "provider": provider,
            "model": model,
            "tokens_generated": tokens_generated,
            "duration_seconds": round(duration_seconds, 2),
            "throughput_tok_s": tp,
            "workflow_velocity_tok_s": workflow_velocity
        }
        with open(STREAM_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # 2. Update cumulative_tokens.json atomically
        _update_cumulative_totals(source, seat, tokens_generated, duration_seconds)
    except Exception as e:
        pass


def _update_cumulative_totals(source: str, seat: str, tokens_generated: int, duration_seconds: float):
    """Atomically reads, updates, and writes cumulative_tokens.json."""
    data = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lifetime_tokens_generated": 0,
        "lifetime_kwh_consumed": 0.0,
        "commercial_api_cost_usd": 0.0,
        "actual_electricity_cost_usd": 0.0,
        "net_dollars_saved_usd": 0.0,
        "percent_saved": 0.0,
        "sources": {
            "swarm_delegations": {"tokens": 0, "runs": 0},
            "web_intercom": {"tokens": 0, "runs": 0},
            "nightly_forge": {"tokens": 0, "runs": 0}
        }
    }

    if os.path.exists(CUMULATIVE_JSON_PATH):
        try:
            with open(CUMULATIVE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    # Determine category
    s_lower = source.lower()
    cat = "swarm_delegations"
    if "intercom" in s_lower or "mice" in s_lower or "foyer" in s_lower:
        cat = "web_intercom"
    elif "forge" in s_lower or "scan" in s_lower or "refine" in s_lower:
        cat = "nightly_forge"

    if cat not in data["sources"]:
        data["sources"][cat] = {"tokens": 0, "runs": 0}

    data["sources"][cat]["tokens"] += tokens_generated
    data["sources"][cat]["runs"] += 1

    data["lifetime_tokens_generated"] += tokens_generated
    data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Power & Energy Calculation
    watts = POWER_PROFILES_WATTS.get(seat, 18.0)
    hours = duration_seconds / 3600.0
    kwh = (watts * hours) / 1000.0
    data["lifetime_kwh_consumed"] = round(data.get("lifetime_kwh_consumed", 0.0) + kwh, 5)

    # Financial Cost Comparison
    total_mtok = data["lifetime_tokens_generated"] / 1000000.0
    comm_cost = round(total_mtok * COMMERCIAL_RATE_PER_1M, 4)
    elec_cost = round(data["lifetime_kwh_consumed"] * ELECTRICITY_RATE_PER_KWH, 4)
    savings = round(max(0.0, comm_cost - elec_cost), 4)
    pct = round((savings / comm_cost * 100.0), 1) if comm_cost > 0 else 0.0

    data["commercial_api_cost_usd"] = comm_cost
    data["actual_electricity_cost_usd"] = elec_cost
    data["net_dollars_saved_usd"] = savings
    data["percent_saved"] = pct

    tmp_path = CUMULATIVE_JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, CUMULATIVE_JSON_PATH)
