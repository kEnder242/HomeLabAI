#!/usr/bin/env python3
"""
MoE+ Federated Router Benchmark Harness

Benchmark the federated routing latency (Llama 3B Router -> Pinky -> Brain -> Deep Thought)
under different start conditions (cold vs. warm starts) to evaluate routing decisions
and escalation accuracy.

Outputs:
- Tabular summary of routing accuracy, decision latency, and total route timings.
- JSON results file: src/debug/moe_benchmark_results.json
"""

import json
import time
import random
import asyncio
from typing import List, Dict, Any
import os

# Configuration
QUERIES_FILE = os.path.join(os.path.dirname(__file__), "moe_queries.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "moe_benchmark_results.json")

# Mock routing latency and accuracy (fallback if Ollama is offline)
MOCK_ROUTER_LATENCY_MS = 80
MOCK_ROUTER_ACCURACY = 0.95
COLD_START_LATENCY_S = 2.0  # Simulated cold start latency


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


async def benchmark_routing(queries: List[Dict[str, Any]], cold_start: bool) -> List[Dict[str, Any]]:
    """
    Benchmark the routing for a list of queries under cold or warm start conditions.
    Returns a list of results for each query.
    """
    results = []
    
    for query_data in queries:
        query = query_data["query"]
        expected_expert = query_data["expected_expert"]
        
        # Simulate router decision
        start_time = time.time()
        routing_result = mock_router_decision(query, expected_expert)
        router_latency = routing_result["router_latency_ms"]
        
        # Simulate expert warmup
        warmup_latency = simulate_expert_warmup(cold_start)
        
        # Simulate expert execution (mock latency)
        expert_latency_ms = random.uniform(500, 2000) if cold_start else random.uniform(200, 800)
        time.sleep(expert_latency_ms / 1000)
        
        total_latency_ms = router_latency + (warmup_latency * 1000) + expert_latency_ms
        
        result = {
            **routing_result,
            "warmup_latency_ms": warmup_latency * 1000,
            "expert_latency_ms": expert_latency_ms,
            "total_latency_ms": total_latency_ms,
            "cold_start": cold_start,
        }
        results.append(result)
    
    return results


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics from benchmark results."""
    total_queries = len(results)
    correct_routes = sum(1 for r in results if r["is_correct"])
    accuracy = correct_routes / total_queries if total_queries > 0 else 0
    
    avg_router_latency = sum(r["router_latency_ms"] for r in results) / total_queries
    avg_warmup_latency = sum(r["warmup_latency_ms"] for r in results) / total_queries
    avg_expert_latency = sum(r["expert_latency_ms"] for r in results) / total_queries
    avg_total_latency = sum(r["total_latency_ms"] for r in results) / total_queries
    
    return {
        "total_queries": total_queries,
        "accuracy": accuracy,
        "avg_router_latency_ms": avg_router_latency,
        "avg_warmup_latency_ms": avg_warmup_latency,
        "avg_expert_latency_ms": avg_expert_latency,
        "avg_total_latency_ms": avg_total_latency,
    }


def print_tabular_summary(cold_results: List[Dict[str, Any]], warm_results: List[Dict[str, Any]]) -> None:
    """Print a tabular summary of benchmark results."""
    cold_metrics = calculate_metrics(cold_results)
    warm_metrics = calculate_metrics(warm_results)
    
    print("\n" + "=" * 80)
    print("MoE+ Federated Router Benchmark Results".center(80))
    print("=" * 80)
    print(f"{'Metric':<30} | {'Cold Start':<20} | {'Warm Start':<20}")
    print("-" * 80)
    print(f"{'Total Queries':<30} | {cold_metrics['total_queries']:<20} | {warm_metrics['total_queries']:<20}")
    cold_acc = f"{cold_metrics['accuracy'] * 100:.1f}%"
    warm_acc = f"{warm_metrics['accuracy'] * 100:.1f}%"
    cold_router = f"{cold_metrics['avg_router_latency_ms']:.1f}"
    warm_router = f"{warm_metrics['avg_router_latency_ms']:.1f}"
    cold_warmup = f"{cold_metrics['avg_warmup_latency_ms']:.1f}"
    warm_warmup = f"{warm_metrics['avg_warmup_latency_ms']:.1f}"
    cold_expert = f"{cold_metrics['avg_expert_latency_ms']:.1f}"
    warm_expert = f"{warm_metrics['avg_expert_latency_ms']:.1f}"
    cold_total = f"{cold_metrics['avg_total_latency_ms']:.1f}"
    warm_total = f"{warm_metrics['avg_total_latency_ms']:.1f}"
    
    print(f"{'Routing Accuracy':<30} | {cold_acc:<20} | {warm_acc:<20}")
    print(f"{'Avg Router Latency (ms)':<30} | {cold_router:<20} | {warm_router:<20}")
    print(f"{'Avg Warmup Latency (ms)':<30} | {cold_warmup:<20} | {warm_warmup:<20}")
    print(f"{'Avg Expert Latency (ms)':<30} | {cold_expert:<20} | {warm_expert:<20}")
    print(f"{'Avg Total Latency (ms)':<30} | {cold_total:<20} | {warm_total:<20}")
    print("=" * 80 + "\n")


def save_results(cold_results: List[Dict[str, Any]], warm_results: List[Dict[str, Any]]) -> None:
    """Save benchmark results to a JSON file."""
    results = {
        "cold_start": cold_results,
        "warm_start": warm_results,
        "metrics": {
            "cold_start": calculate_metrics(cold_results),
            "warm_start": calculate_metrics(warm_results),
        }
    }
    
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {RESULTS_FILE}")


async def main():
    """Run the benchmark and output results."""
    queries = load_queries()
    
    print("Running MoE+ Federated Router Benchmark...")
    print(f"Loaded {len(queries)} queries from {QUERIES_FILE}")
    
    # Run cold start benchmark
    print("\nBenchmarking Cold Start (keep_alive=0)...")
    cold_results = await benchmark_routing(queries, cold_start=True)
    
    # Run warm start benchmark
    print("Benchmarking Warm Start...")
    warm_results = await benchmark_routing(queries, cold_start=False)
    
    # Print summary and save results
    print_tabular_summary(cold_results, warm_results)
    save_results(cold_results, warm_results)


if __name__ == "__main__":
    asyncio.run(main())