"""MoE+ Federated Router Benchmark with single-pass dual cold/warm telemetry."""

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List

from prometheus_client import start_http_server

from moe_prometheus_gauges import (
    moe_expert_latency_seconds,
    moe_router_latency_seconds,
    moe_routing_accuracy,
    moe_total_latency_seconds,
    moe_warmup_latency_seconds,
)

QUERIES_FILE = "/home/jallred/Dev_Lab/HomeLabAI/src/debug/moe_benchmark_queries.json"
RESULTS_FILE = "/home/jallred/Dev_Lab/HomeLabAI/src/debug/moe_routing_results.json"

# Mock parameters
MOCK_ROUTER_LATENCY_MS = 50
MOCK_ROUTER_ACCURACY = 0.85
COLD_START_LATENCY_S = 2.0


def load_queries() -> List[Dict[str, Any]]:
    """Load the dataset of queries and expected experts."""
    with open(QUERIES_FILE, "r") as f:
        return json.load(f)


def mock_router_decision(query: str, expected_expert: str) -> Dict[str, Any]:
    """
    Simulate a router decision with mock latency and accuracy.
    Returns a dictionary with the decision, latency, and correctness.
    """
    time.sleep(MOCK_ROUTER_LATENCY_MS / 1000)

    # Simulate routing accuracy
    if random.random() <= MOCK_ROUTER_ACCURACY:
        chosen_expert = expected_expert
    else:
        experts = ["coding", "deep_reasoning", "conversation", "research"]
        experts.remove(expected_expert)
        chosen_expert = random.choice(experts)

    return {
        "query": query,
        "expected_expert": expected_expert,
        "chosen_expert": chosen_expert,
        "is_correct": chosen_expert == expected_expert,
        "router_latency_ms": MOCK_ROUTER_LATENCY_MS,
    }


def simulate_expert_warmup(cold_start: bool) -> float:
    """Simulate expert model warmup latency."""
    if cold_start:
        time.sleep(COLD_START_LATENCY_S)
        return COLD_START_LATENCY_S
    return 0.0


async def benchmark_routing(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Single-pass benchmark: simulates both cold and warm starts for each query
    and emits dual telemetry (cold + warm metrics) in one event per query.
    """
    results = []

    for query_data in queries:
        query = query_data["query"]
        expected_expert = query_data["expected_expert"]

        # Simulate router decision (shared between cold and warm)
        start_time = time.time()
        routing_result = mock_router_decision(query, expected_expert)
        router_latency = routing_result["router_latency_ms"]

        # --- Cold start simulation ---
        cold_warmup_latency = simulate_expert_warmup(cold_start=True)
        cold_expert_latency_ms = random.uniform(500, 2000)
        time.sleep(cold_expert_latency_ms / 1000)
        cold_total_latency_ms = router_latency + (cold_warmup_latency * 1000) + cold_expert_latency_ms

        # --- Warm start simulation ---
        warm_warmup_latency = simulate_expert_warmup(cold_start=False)
        warm_expert_latency_ms = random.uniform(200, 800)
        time.sleep(warm_expert_latency_ms / 1000)
        warm_total_latency_ms = router_latency + (warm_warmup_latency * 1000) + warm_expert_latency_ms

        # Assemble dual telemetry result
        result = {
            "query": query,
            "expected_expert": expected_expert,
            "chosen_expert": routing_result["chosen_expert"],
            "cold_start_metrics": {
                "router_latency_ms": router_latency,
                "warmup_latency_ms": cold_warmup_latency * 1000,
                "expert_latency_ms": cold_expert_latency_ms,
                "total_latency_ms": cold_total_latency_ms,
                "is_correct": routing_result["is_correct"],
            },
            "warm_start_metrics": {
                "router_latency_ms": router_latency,
                "warmup_latency_ms": warm_warmup_latency * 1000,
                "expert_latency_ms": warm_expert_latency_ms,
                "total_latency_ms": warm_total_latency_ms,
                "is_correct": routing_result["is_correct"],
            },
        }
        results.append(result)

        # Emit dual Prometheus metrics (cold + warm for the same query)
        for start_type, metrics in [("cold", result["cold_start_metrics"]), ("warm", result["warm_start_metrics"])]:
            moe_router_latency_seconds.labels(start_type=start_type).set(metrics["router_latency_ms"] / 1000.0)
            moe_warmup_latency_seconds.labels(start_type=start_type).set(metrics["warmup_latency_ms"] / 1000.0)
            moe_expert_latency_seconds.labels(start_type=start_type).set(metrics["expert_latency_ms"] / 1000.0)
            moe_total_latency_seconds.labels(start_type=start_type).set(metrics["total_latency_ms"] / 1000.0)
            moe_routing_accuracy.labels(start_type=start_type).set(1.0 if metrics["is_correct"] else 0.0)

    return results


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics for both cold and warm start results."""
    n = len(results)

    def _agg(key: str, prefix: str) -> float:
        return sum(r[f"{prefix}_start_metrics"][key] for r in results) / n if n > 0 else 0.0

    cold = {
        "total_queries": n,
        "correct_routes": sum(1 for r in results if r["cold_start_metrics"]["is_correct"]),
        "avg_router_latency_ms": _agg("router_latency_ms", "cold"),
        "avg_warmup_latency_ms": _agg("warmup_latency_ms", "cold"),
        "avg_expert_latency_ms": _agg("expert_latency_ms", "cold"),
        "avg_total_latency_ms": _agg("total_latency_ms", "cold"),
    }
    cold["accuracy"] = cold["correct_routes"] / cold["total_queries"] if cold["total_queries"] > 0 else 0.0

    warm = {
        "total_queries": n,
        "correct_routes": sum(1 for r in results if r["warm_start_metrics"]["is_correct"]),
        "avg_router_latency_ms": _agg("router_latency_ms", "warm"),
        "avg_warmup_latency_ms": _agg("warmup_latency_ms", "warm"),
        "avg_expert_latency_ms": _agg("expert_latency_ms", "warm"),
        "avg_total_latency_ms": _agg("total_latency_ms", "warm"),
    }
    warm["accuracy"] = warm["correct_routes"] / warm["total_queries"] if warm["total_queries"] > 0 else 0.0

    return {"cold": cold, "warm": warm}


def print_tabular_summary(results: List[Dict[str, Any]]) -> None:
    """Print a tabular summary of benchmark results for both cold and warm starts."""
    metrics = calculate_metrics(results)
    cold_metrics = metrics["cold"]
    warm_metrics = metrics["warm"]

    print("\n" + "=" * 80)
    print("MoE+ Federated Router Benchmark Results".center(80))
    print("=" * 80)
    print(f"{'Metric':<30} | {'Cold Start':<20} | {'Warm Start':<20}")
    print("-" * 80)
    print(f"{'Total Queries':<30} | {cold_metrics['total_queries']:<20} | {warm_metrics['total_queries']:<20}")
    cold_acc = f"{cold_metrics['accuracy'] * 100:.1f}%"
    warm_acc = f"{warm_metrics['accuracy'] * 100:.1f}%"
    print(f"{'Routing Accuracy':<30} | {cold_acc:<20} | {warm_acc:<20}")
    print(f"{'Avg Router Latency (ms)':<30} | {cold_metrics['avg_router_latency_ms']:<20.1f} | {warm_metrics['avg_router_latency_ms']:<20.1f}")
    print(f"{'Avg Warmup Latency (ms)':<30} | {cold_metrics['avg_warmup_latency_ms']:<20.1f} | {warm_metrics['avg_warmup_latency_ms']:<20.1f}")
    print(f"{'Avg Expert Latency (ms)':<30} | {cold_metrics['avg_expert_latency_ms']:<20.1f} | {warm_metrics['avg_expert_latency_ms']:<20.1f}")
    print(f"{'Avg Total Latency (ms)':<30} | {cold_metrics['avg_total_latency_ms']:<20.1f} | {warm_metrics['avg_total_latency_ms']:<20.1f}")
    print("=" * 80 + "\n")


def save_results(results: List[Dict[str, Any]]) -> None:
    """Save benchmark results to a JSON file."""
    metrics = calculate_metrics(results)

    output = {
        "cold_start_metrics": [
            {
                "query": r["query"],
                "expected_expert": r["expected_expert"],
                "chosen_expert": r["chosen_expert"],
                **r["cold_start_metrics"],
            }
            for r in results
        ],
        "warm_start_metrics": [
            {
                "query": r["query"],
                "expected_expert": r["expected_expert"],
                "chosen_expert": r["chosen_expert"],
                **r["warm_start_metrics"],
            }
            for r in results
        ],
        "metrics": metrics,
    }

    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Results saved to {RESULTS_FILE}")


async def main():
    """Run the benchmark and output results."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Start Prometheus metrics server
    start_http_server(8010)
    logging.info("Prometheus metrics endpoint active on http://localhost:8010")

    queries = load_queries()

    print("Running MoE+ Federated Router Benchmark...")
    print(f"Loaded {len(queries)} queries from {QUERIES_FILE}")

    # Single-pass benchmark: both cold and warm in one run
    print("\nBenchmarking Cold and Warm Start (single-pass)...")
    results = await benchmark_routing(queries)

    # Print summary and save results
    print_tabular_summary(results)
    save_results(results)

    # Keep-alive loop so Prometheus can scrape metrics
    while True:
        time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
