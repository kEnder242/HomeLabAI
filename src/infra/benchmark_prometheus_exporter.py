"""
[FEAT-690] Benchmark Prometheus Exporter (:8011)
Bridges on-disk JSON streams (round_table_deltas.json, live_usage_stream.jsonl)
into Prometheus Gauges scraped by 'moe-plus-model-benchmarks' (:8011).
"""
import http.server
import json
import logging
import os
import sys
import threading
from typing import Any

from prometheus_client import CollectorRegistry, Gauge, generate_latest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BENCH_EXPORTER")

PORT = 8011
REGISTRY = CollectorRegistry()

# 1. Round Table Stage Durations (used by panel 5)
STAGE_DURATIONS = Gauge(
    "moe_stage_duration_seconds",
    "Deliberation & Round Table Stage Durations",
    ["stage"],
    registry=REGISTRY,
)

# 2. Router Latency (used by panel 6)
ROUTER_LATENCY = Gauge(
    "moe_router_latency_seconds",
    "Intent routing and triage latency in seconds",
    ["start_type"],
    registry=REGISTRY,
)

# 3. Model TTFT & ITL & Throughput (used by panel 7)
MODEL_TTFT = Gauge(
    "moe_model_ttft_seconds",
    "Time to first token in seconds",
    ["node"],
    registry=REGISTRY,
)
MODEL_ITL = Gauge(
    "moe_model_itl_seconds",
    "Inter-token latency in seconds",
    ["node"],
    registry=REGISTRY,
)
MODEL_THROUGHPUT = Gauge(
    "moe_model_throughput_tok_s",
    "Model generation throughput in tokens per second",
    ["node"],
    registry=REGISTRY,
)
ROUND_TABLE_TURN = Gauge(
    "moe_round_table_turn_number",
    "Monotonic Turn ID of last round table deliberation",
    registry=REGISTRY,
)


def update_from_round_table_entry(entry: dict[str, Any]):
    deltas = entry.get("deltas_elapsed_s") or entry.get("deltas") or {}
    triage = float(deltas.get("triage", 0.0))
    pinky_stance = float(deltas.get("pinky_stance", 0.0))
    brain_arch = float(deltas.get("brain_arch", 0.0))
    oracle = float(deltas.get("oracle", 0.0))
    pinky_judgment = float(deltas.get("pinky_judgment", 0.0))
    total = float(entry.get("total_elapsed_s", 0.0))

    STAGE_DURATIONS.labels(stage="triage").set(triage)
    STAGE_DURATIONS.labels(stage="pinky_stance").set(pinky_stance)
    STAGE_DURATIONS.labels(stage="brain_arch").set(brain_arch)
    STAGE_DURATIONS.labels(stage="oracle").set(oracle)
    STAGE_DURATIONS.labels(stage="pinky_judgment").set(pinky_judgment)
    STAGE_DURATIONS.labels(stage="total_pipeline").set(total)

    ROUTER_LATENCY.labels(start_type="warm").set(triage)
    if "turn" in entry:
        ROUND_TABLE_TURN.set(float(entry["turn"]))
    logger.info(
        f"[PROMETHEUS PUSH] Round Table Turn {entry.get('turn')} ingested. Total: {total}s"
    )


def update_from_usage_stream_entry(entry: dict[str, Any]):
    node = entry.get("seat") or entry.get("node") or "Hybrid GPU (2080 Ti + Arc B580)"
    tp = entry.get("throughput_tok_s")
    dur = float(entry.get("duration_seconds", 0.0))
    toks = float(entry.get("tokens_generated", 0))

    if tp and float(tp) > 0:
        tp_float = float(tp)
        MODEL_THROUGHPUT.labels(node=node).set(tp_float)
        MODEL_ITL.labels(node=node).set(1.0 / tp_float)
    if "ttft_s" in entry:
        MODEL_TTFT.labels(node=node).set(float(entry["ttft_s"]))
    elif "ttft_ms" in entry:
        MODEL_TTFT.labels(node=node).set(float(entry["ttft_ms"]) / 1000.0)
    logger.info(
        f"[PROMETHEUS PUSH] Usage stream entry ingested for {node}: {toks} tok / {dur}s"
    )


class ExporterHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence routine scrape logs to avoid terminal noise
        return

    def do_GET(self):
        if self.path in ("/metrics", "/"):
            data = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/health":
            body = b'{"status": "ONLINE", "port": 8011}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/push":
            content_len = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_len)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                if (
                    "deltas" in payload
                    or "deltas_elapsed_s" in payload
                    or "checkpoints_elapsed_s" in payload
                ):
                    update_from_round_table_entry(payload)
                elif "tokens_generated" in payload or "throughput_tok_s" in payload:
                    update_from_usage_stream_entry(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "INGESTED"}\n')
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'{{"error": "{str(e)}"}}\n'.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = PORT):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), ExporterHandler)
    logger.info(
        f"[EXPORTER] Benchmark Prometheus Exporter listening on http://127.0.0.1:{port}/metrics"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
