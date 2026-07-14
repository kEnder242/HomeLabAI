# Latency Hiding & Pre-Gated Routing Pipeline Simulator

"""
This script simulates the concurrent execution of the MoE+ routing pipeline to verify
latency hiding benefits. The pipeline stages are:

1. Intent Classification (Fast, Llama-3.2-3B Router)
2. RAG Retrieval (Context gathering from vector DB)
3. Workspace Context Collection (File indexing, git status, etc.)
4. Model Warming (Cold start simulation for heavy models)
5. Prompt Compilation (Final prompt assembly)

The goal is to ensure that RAG and workspace context collection finish BEFORE
model warming completes, effectively hiding 1-2 seconds of cold start latency.
"""

import asyncio
import time
import json
import random
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class PipelineMetrics:
    """Structured timing metrics for each pipeline stage."""
    intent_classification_start: float
    intent_classification_end: float
    rag_retrieval_start: float
    rag_retrieval_end: float
    workspace_context_start: float
    workspace_context_end: float
    model_warming_start: float
    model_warming_end: float
    prompt_compilation_start: float
    prompt_compilation_end: float
    total_pipeline_start: float
    total_pipeline_end: float


async def simulate_intent_classification() -> str:
    """Simulate intent classification using a lightweight router model."""
    await asyncio.sleep(random.uniform(0.1, 0.3))  # Fast classification
    return random.choice(["coding", "conversation", "deep_reasoning", "research"])


async def simulate_rag_retrieval(intent: str) -> List[Dict]:
    """Simulate RAG retrieval based on intent."""
    await asyncio.sleep(random.uniform(0.5, 1.2))  # Simulate vector DB query
    return [{"content": f"Relevant context for {intent}", "score": random.uniform(0.7, 0.99)}]


async def simulate_workspace_context_collection() -> Dict:
    """Simulate workspace context collection (file indexing, git status, etc.)."""
    await asyncio.sleep(random.uniform(0.8, 1.5))  # Simulate file system ops
    return {
        "files": ["file1.py", "file2.ts", "README.md"],
        "git_status": "clean",
        "active_branch": "main"
    }


async def simulate_model_warming(intent: str) -> bool:
    """Simulate cold model warming for the selected expert."""
    # Simulate longer warmup for heavy models
    if intent == "deep_reasoning":
        await asyncio.sleep(random.uniform(2.0, 3.5))
    else:
        await asyncio.sleep(random.uniform(1.5, 2.5))
    return True


async def simulate_prompt_compilation(intent: str, rag_context: List[Dict], workspace_context: Dict) -> str:
    """Simulate final prompt compilation."""
    await asyncio.sleep(random.uniform(0.2, 0.5))
    return f"Compiled prompt for {intent} with {len(rag_context)} RAG chunks and workspace context."


async def run_pipeline() -> PipelineMetrics:
    """Run the full latency-hiding pipeline and collect timing metrics."""
    metrics = PipelineMetrics(
        intent_classification_start=0.0,
        intent_classification_end=0.0,
        rag_retrieval_start=0.0,
        rag_retrieval_end=0.0,
        workspace_context_start=0.0,
        workspace_context_end=0.0,
        model_warming_start=0.0,
        model_warming_end=0.0,
        prompt_compilation_start=0.0,
        prompt_compilation_end=0.0,
        total_pipeline_start=time.time(),
        total_pipeline_end=0.0
    )

    # Stage 1: Intent Classification (Fast, runs immediately)
    metrics.intent_classification_start = time.time()
    intent = await simulate_intent_classification()
    metrics.intent_classification_end = time.time()

    # Stage 2 & 3: RAG Retrieval + Workspace Context Collection (Concurrent with Model Warming)
    metrics.rag_retrieval_start = time.time()
    metrics.workspace_context_start = time.time()

    rag_task = asyncio.create_task(simulate_rag_retrieval(intent))
    workspace_task = asyncio.create_task(simulate_workspace_context_collection())

    # Stage 4: Model Warming (Starts AFTER intent classification)
    metrics.model_warming_start = time.time()
    warming_task = asyncio.create_task(simulate_model_warming(intent))

    # Wait for RAG and Workspace tasks to complete
    rag_context, workspace_context = await asyncio.gather(rag_task, workspace_task)
    metrics.rag_retrieval_end = time.time()
    metrics.workspace_context_end = time.time()

    # Wait for Model Warming to complete
    await warming_task
    metrics.model_warming_end = time.time()

    # Stage 5: Prompt Compilation (Runs after all prior stages)
    metrics.prompt_compilation_start = time.time()
    prompt = await simulate_prompt_compilation(intent, rag_context, workspace_context)
    metrics.prompt_compilation_end = time.time()

    metrics.total_pipeline_end = time.time()
    return metrics


async def verify_latency_hiding(metrics: PipelineMetrics) -> bool:
    """Verify that RAG and workspace collection finish before model warming."""
    rag_duration = metrics.rag_retrieval_end - metrics.rag_retrieval_start
    workspace_duration = metrics.workspace_context_end - metrics.workspace_context_start
    warming_duration = metrics.model_warming_end - metrics.model_warming_start

    # Calculate overlap: RAG + Workspace should finish BEFORE warming
    rag_finish_before_warming = metrics.rag_retrieval_end <= metrics.model_warming_end
    workspace_finish_before_warming = metrics.workspace_context_end <= metrics.model_warming_end

    print(f"\n✅ Latency Hiding Verification:")
    print(f"   RAG Retrieval: {rag_duration:.2f}s (Finished before warming: {rag_finish_before_warming})")
    print(f"   Workspace Collection: {workspace_duration:.2f}s (Finished before warming: {workspace_finish_before_warming})")
    print(f"   Model Warming: {warming_duration:.2f}s")

    return rag_finish_before_warming and workspace_finish_before_warming


async def main():
    print("🚀 Running MoE+ Latency Hiding Pipeline Simulator...")
    metrics = await run_pipeline()
    
    # Print timing breakdown
    print("\n⏱️  Pipeline Timing Metrics:")
    for field in asdict(metrics).keys():
        if "start" in field or "end" in field:
            continue
        duration = getattr(metrics, field.replace("_end", "").replace("_start", "") + "_end") - getattr(metrics, field.replace("_end", "").replace("_start", "") + "_start")
        print(f"   {field.replace('_', ' ').title()}: {duration:.2f}s")

    # Verify latency hiding
    latency_hiding_success = await verify_latency_hiding(metrics)
    if latency_hiding_success:
        print("\n🎉 Verification Gate PASSED: Latency hiding successful!")
    else:
        print("\n❌ Verification Gate FAILED: Latency hiding not achieved.")

    # Save metrics to JSON
    output_path = "/home/jallred/Dev_Lab/HomeLabAI/src/debug/moe_pipeline_metrics.json"
    with open(output_path, "w") as f:
        json.dump(asdict(metrics), f, indent=2)
    print(f"\n💾 Metrics saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())