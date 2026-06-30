"""
[FEAT-T21] Silicon Benchmarking Engine — run_evals.py
BKM-032: LLM-as-a-Judge evaluation harness.

Usage:
    python run_evals.py                    # run all prompts
    python run_evals.py --tag telemetry    # run only tagged prompts
    python run_evals.py --model ollama     # target Ollama instead of vLLM
    python run_evals.py --dry-run          # show prompts, don't execute
    python run_evals.py --list-tags        # show available tags

Output:
    HomeLabAI/logs/benchmarks.jsonl        # append-only benchmark ledger
    pager_activity.json                    # watchdog alerts if score drops
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

import aiohttp

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
LAB_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

BENCHMARKS_LEDGER = os.path.join(LAB_DIR, "logs", "benchmarks.jsonl")
DCGM_URL = os.environ.get("DCGM_URL", "http://localhost:9400/metrics")
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8088/v1/chat/completions")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "unified-base")
VLLM_MODELS_URL = os.environ.get("VLLM_MODELS_URL", "http://localhost:8088/v1/models")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

# BKM-032 Watchdog threshold: alert if avg judge score drops below this
WATCHDOG_SCORE_THRESHOLD = float(os.environ.get("BENCH_SCORE_THRESHOLD", "3.0"))
WATCHDOG_WINDOW = int(os.environ.get("BENCH_WATCHDOG_WINDOW", "5"))  # last N runs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EVAL] %(message)s")
log = logging.getLogger("eval")

# ---------------------------------------------------------------------------
# Eval Prompt Bank
# BKM: Prompts are organized by tag. Add new prompts here to extend coverage.
# ---------------------------------------------------------------------------
EVAL_PROMPTS = [
    # --- Domain: telemetry ---
    {
        "id": "tlm-001",
        "tags": ["telemetry", "baseline", "silicon"],
        "prompt": "What is RAPL and how is it used for power capping in Intel CPUs?",
        "rubric": "Should explain Running Average Power Limit, MSR registers, power domains (PKG, DRAM, CORE), and practical use in telemetry.",
    },
    {
        "id": "tlm-002",
        "tags": ["telemetry", "baseline", "nvidia"],
        "prompt": "Explain the difference between DCGM and nvidia-smi for GPU telemetry collection at scale.",
        "rubric": "Should contrast pull vs push models, Prometheus integration, enterprise vs desktop use, and per-process visibility.",
    },
    {
        "id": "tlm-003",
        "tags": ["telemetry", "redfish"],
        "prompt": "How does the Redfish API expose power and thermal telemetry for BMC-managed servers?",
        "rubric": "Should mention /redfish/v1/Chassis, Thermal and Power schemas, polling vs SSE events, and vendor extensions.",
    },
    {
        "id": "tlm-004",
        "tags": ["telemetry", "pcie"],
        "prompt": "What PCIe telemetry counters are most useful for detecting link degradation in a GPU cluster?",
        "rubric": "Should cover correctable/uncorrectable errors, link speed/width negotiation, replay counters, and AER registers.",
    },
    # --- Domain: lab history ---
    {
        "id": "hist-001",
        "tags": ["history", "lab", "archive"],
        "prompt": "Describe the key milestones in the development of this lab's AI engine from v1 to v5.",
        "rubric": "Should reference Bicameral architecture, MCP nodes, vLLM migration, Multi-LoRA, and V5 Foyer Router.",
    },
    {
        "id": "hist-002",
        "tags": ["history", "lab", "silicon"],
        "prompt": "What silicon hardware does this lab use and what are its key constraints?",
        "rubric": "Should mention RTX 2080 Ti (11GB VRAM, Compute 7.5), Z87 platform, AWQ quantization necessity, bfloat16 limitation.",
    },
    # --- Domain: inference ---
    {
        "id": "inf-001",
        "tags": ["inference", "vllm", "baseline"],
        "prompt": "What is the difference between continuous batching and static batching in LLM inference servers?",
        "rubric": "Should explain iteration-level scheduling, GPU utilization improvements, latency vs throughput trade-offs.",
    },
    {
        "id": "inf-002",
        "tags": ["inference", "quantization"],
        "prompt": "Compare AWQ and GPTQ quantization for 4-bit LLM deployment on consumer GPUs.",
        "rubric": "Should cover weight-only vs activation-aware, calibration process, perplexity impact, and inference speed differences.",
    },
    {
        "id": "inf-003",
        "tags": ["inference", "lora"],
        "prompt": "How does Multi-LoRA serving work in vLLM and what are the memory implications?",
        "rubric": "Should explain LoRA adapter pooling, rank decomposition, dynamic swapping, shared base model VRAM footprint.",
    },
    # --- Domain: tco ---
    {
        "id": "tco-001",
        "tags": ["tco", "economics", "silicon"],
        "prompt": "Explain how to calculate the total cost of ownership for running a 7B parameter LLM locally vs cloud API.",
        "rubric": "Should include amortized hardware cost, power draw (kWh * rate), inference throughput, and break-even analysis.",
    },
]

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkRun:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    prompt_id: str = ""
    tags: list = field(default_factory=list)
    prompt: str = ""
    response: str = ""
    # Engine
    engine: str = ""         # VLLM | OLLAMA
    model: str = ""
    quantization: str = ""   # AWQ | GGUF | FP16 | unknown
    # Timing
    ttft_ms: float = 0.0
    tokens_per_sec: float = 0.0
    total_tokens: int = 0
    duration_s: float = 0.0
    # Silicon
    gpu_power_w: float = 0.0
    gpu_temp_c: float = 0.0
    vram_used_mb: float = 0.0
    joules_per_token: float = 0.0
    tco_usd: float = 0.0     # synthetic, $0.10/kWh
    # Evaluation
    judge_score: int = 0     # 1-5
    judge_reasoning: str = ""
    judge_model: str = ""
    rubric: str = ""


# ---------------------------------------------------------------------------
# DCGM Snapshot (reuse telemetry_collector if available, else inline)
# ---------------------------------------------------------------------------
def _parse_prom(text: str, metric: str) -> float:
    for line in text.splitlines():
        if line.startswith(metric) and not line.startswith("#"):
            try:
                return float(line.rsplit(" ", 1)[-1])
            except ValueError:
                pass
    return 0.0


async def _gpu_snapshot(session: aiohttp.ClientSession) -> dict:
    try:
        async with session.get(DCGM_URL, timeout=aiohttp.ClientTimeout(total=2)) as r:
            if r.status == 200:
                text = await r.text()
                return {
                    "gpu_power_w": _parse_prom(text, "DCGM_FI_DEV_POWER_USAGE"),
                    "gpu_temp_c": _parse_prom(text, "DCGM_FI_DEV_GPU_TEMP"),
                    "vram_used_mb": _parse_prom(text, "DCGM_FI_DEV_FB_USED"),
                }
    except Exception:
        pass
    return {"gpu_power_w": 0.0, "gpu_temp_c": 0.0, "vram_used_mb": 0.0}


# ---------------------------------------------------------------------------
# Inference Runners
# ---------------------------------------------------------------------------
async def _run_vllm(session: aiohttp.ClientSession, prompt: str) -> tuple[str, float, int, float]:
    """Returns (response_text, ttft_ms, token_count, duration_s)."""
    payload = {
        "model": VLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.0,
        "stream": True,
    }
    t0 = time.time()
    ttft_ms = 0.0
    full = ""
    token_count = 0
    first = True
    try:
        async with session.post(VLLM_URL, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as r:
            if r.status != 200:
                err = await r.text()
                raise RuntimeError(f"vLLM {r.status}: {err[:200]}")
            async for line in r.content:
                if line:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: ") and "[DONE]" not in decoded:
                        try:
                            data = json.loads(decoded[6:])
                            token = data["choices"][0]["delta"].get("content", "")
                            if token:
                                if first:
                                    ttft_ms = (time.time() - t0) * 1000.0
                                    first = False
                                full += token
                                token_count += 1
                        except Exception:
                            pass
    except Exception as e:
        log.error(f"vLLM run failed: {e}")
        full = f"[ERROR] {e}"
    duration_s = time.time() - t0
    return full, ttft_ms, token_count, duration_s


async def _run_ollama(session: aiohttp.ClientSession, prompt: str) -> tuple[str, float, int, float]:
    """Returns (response_text, ttft_ms, token_count, duration_s)."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {"temperature": 0.0, "num_predict": 400},
    }
    t0 = time.time()
    ttft_ms = 0.0
    full = ""
    token_count = 0
    first = True
    try:
        async with session.post(OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as r:
            if r.status != 200:
                raise RuntimeError(f"Ollama {r.status}")
            async for line in r.content:
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        token = data.get("message", {}).get("content", "")
                        if token:
                            if first:
                                ttft_ms = (time.time() - t0) * 1000.0
                                first = False
                            full += token
                            token_count += 1
                        if data.get("done"):
                            break
                    except Exception:
                        pass
    except Exception as e:
        log.error(f"Ollama run failed: {e}")
        full = f"[ERROR] {e}"
    duration_s = time.time() - t0
    return full, ttft_ms, token_count, duration_s


# ---------------------------------------------------------------------------
# LLM-as-a-Judge
# BKM-032: Cynical Curator rubric — score 1-5, mandatory JSON output.
# ---------------------------------------------------------------------------
JUDGE_SYSTEM = """You are a strict technical evaluator. Score responses 1-5.
Output ONLY valid JSON: {"score": <int 1-5>, "reasoning": "<one sentence>"}

Scoring rubric:
5 = Accurate, complete, specific, cites correct technical details
4 = Mostly accurate, minor gaps or imprecision
3 = Partially correct, missing key concepts
2 = Superficial or contains errors
1 = Wrong, hallucinated, or irrelevant"""


async def _judge_response(
    session: aiohttp.ClientSession, prompt: str, response: str, rubric: str, engine: str
) -> tuple[int, str, str]:
    """Returns (score 1-5, reasoning, judge_model)."""
    judge_query = (
        f"QUESTION: {prompt}\n\n"
        f"RUBRIC: {rubric}\n\n"
        f"RESPONSE TO EVALUATE:\n{response[:1500]}\n\n"
        "Score this response 1-5 and output JSON only."
    )

    judge_model = OLLAMA_MODEL
    try:
        # Prefer Ollama for judging (cheaper, always available)
        payload = {
            "model": judge_model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": judge_query},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 150},
        }
        async with session.post(
            OLLAMA_URL.replace("/api/chat", "/api/chat"),
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as r:
            if r.status == 200:
                data = await r.json()
                raw = data.get("message", {}).get("content", "")
                # Extract JSON block
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    score = int(parsed.get("score", 0))
                    reasoning = str(parsed.get("reasoning", ""))
                    if 1 <= score <= 5:
                        return score, reasoning, judge_model
    except Exception as e:
        log.warning(f"Judge call failed: {e}")
    return 0, "Judge unavailable", judge_model


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------
def _compute_economics(power_w: float, duration_s: float, tokens: int) -> tuple[float, float]:
    """Returns (joules_per_token, tco_usd)."""
    if tokens <= 0 or duration_s <= 0:
        return 0.0, 0.0
    joules = power_w * duration_s
    j_per_tok = joules / tokens
    energy_wh = joules / 3600.0
    tco = energy_wh / 1000.0 * 0.10  # $0.10/kWh
    return round(j_per_tok, 6), round(tco, 10)


# ---------------------------------------------------------------------------
# Ledger Write
# ---------------------------------------------------------------------------
def _append_ledger(run: BenchmarkRun) -> None:
    os.makedirs(os.path.dirname(BENCHMARKS_LEDGER), exist_ok=True)
    with open(BENCHMARKS_LEDGER, "a") as f:
        f.write(json.dumps(asdict(run)) + "\n")


# ---------------------------------------------------------------------------
# BKM-032 Watchdog
# ---------------------------------------------------------------------------
def _watchdog_check(score: int, prompt_id: str) -> None:
    """
    [BKM-032] Fires pager alert if recent judge scores fall below threshold.
    Checks the last WATCHDOG_WINDOW entries in benchmarks.jsonl.
    """
    try:
        if not os.path.exists(BENCHMARKS_LEDGER):
            return
        with open(BENCHMARKS_LEDGER, "r") as f:
            lines = f.readlines()

        recent = []
        for line in lines[-WATCHDOG_WINDOW:]:
            try:
                r = json.loads(line.strip())
                if r.get("judge_score", 0) > 0:
                    recent.append(r["judge_score"])
            except Exception:
                pass

        if len(recent) < 2:
            return

        avg = sum(recent) / len(recent)
        if avg < WATCHDOG_SCORE_THRESHOLD:
            msg = (
                f"[BKM-032] Bench quality degradation: avg score {avg:.1f} "
                f"(threshold {WATCHDOG_SCORE_THRESHOLD}) over last {len(recent)} runs. "
                f"Last prompt: {prompt_id}"
            )
            log.warning(msg)
            try:
                from infra.pager_relay import trigger_pager
                trigger_pager(msg, severity="WARNING", source="BenchWatchdog")
            except Exception:
                pass
    except Exception as e:
        log.debug(f"Watchdog check failed: {e}")


# ---------------------------------------------------------------------------
# Model Name Resolution
# ---------------------------------------------------------------------------
def _humanize_model_path(path: str) -> str:
    """Convert a filesystem model path to a human-readable name.
    e.g. '/speedy/models/llama-3.2-3b-instruct-awq' -> 'Llama-3.2-3B-Instruct-AWQ'
    """
    base = os.path.basename(path.rstrip("/"))
    # Title-case each segment, preserve version numbers and acronyms
    parts = base.split("-")
    result = []
    for p in parts:
        if p.upper() in ("AWQ", "GPTQ", "GGUF", "FP16", "BF16"):
            result.append(p.upper())
        elif re.match(r'^\d', p):  # starts with digit (version/size)
            result.append(p.upper() if len(p) <= 3 else p)
        else:
            result.append(p.capitalize())
    return "-".join(result)


async def _resolve_vllm_model_name(session: aiohttp.ClientSession) -> tuple[str, str]:
    """Query vLLM /v1/models to get the real model path and quantization.
    Returns (human_name, quantization).
    Falls back to VLLM_MODEL env var if the endpoint is unavailable.
    """
    try:
        async with session.get(VLLM_MODELS_URL, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                models = data.get("data", [])
                if models:
                    model_id = models[0].get("id", VLLM_MODEL)
                    human = _humanize_model_path(model_id)
                    # Detect quantization from the path
                    lower = model_id.lower()
                    if "awq" in lower:
                        quant = "AWQ"
                    elif "gptq" in lower:
                        quant = "GPTQ"
                    elif "gguf" in lower:
                        quant = "GGUF"
                    else:
                        quant = "FP16"
                    log.info(f"Resolved vLLM model: {human} ({quant}) from {model_id}")
                    return human, quant
    except Exception as e:
        log.warning(f"Could not resolve vLLM model name: {e}. Using fallback.")
    return VLLM_MODEL, "AWQ"


# ---------------------------------------------------------------------------
# Main Eval Loop
# ---------------------------------------------------------------------------
async def run_eval(prompts: list, engine: str = "vllm", dry_run: bool = False) -> list[BenchmarkRun]:
    runs = []

    # Resolve the actual model identity at runtime
    async with aiohttp.ClientSession() as probe:
        if engine == "vllm":
            model_name, quantization = await _resolve_vllm_model_name(probe)
        else:
            model_name = OLLAMA_MODEL
            quantization = "Q4_0"  # Ollama default quantization

    async with aiohttp.ClientSession() as session:
        for i, p in enumerate(prompts):
            log.info(f"[{i+1}/{len(prompts)}] Running: {p['id']} | {p['tags']}")

            if dry_run:
                log.info(f"  PROMPT: {p['prompt'][:80]}...")
                continue

            # 1. Snap GPU before
            gpu_before = await _gpu_snapshot(session)

            # 2. Run inference
            if engine == "vllm":
                response, ttft_ms, tokens, duration_s = await _run_vllm(session, p["prompt"])
            else:
                response, ttft_ms, tokens, duration_s = await _run_ollama(session, p["prompt"])

            # 3. Snap GPU after (use avg of before/after)
            gpu_after = await _gpu_snapshot(session)
            avg_power = (gpu_before["gpu_power_w"] + gpu_after["gpu_power_w"]) / 2.0

            # 4. Economics
            j_per_tok, tco = _compute_economics(avg_power, duration_s, tokens)
            tps = tokens / duration_s if duration_s > 0 else 0.0

            # 5. Judge
            score, reasoning, judge_model = await _judge_response(
                session, p["prompt"], response, p.get("rubric", ""), engine
            )

            # 6. Assemble
            run = BenchmarkRun(
                prompt_id=p["id"],
                tags=p["tags"],
                prompt=p["prompt"],
                response=response[:2000],  # cap stored response
                engine=engine.upper(),
                model=model_name,
                quantization=quantization,
                ttft_ms=round(ttft_ms, 2),
                tokens_per_sec=round(tps, 2),
                total_tokens=tokens,
                duration_s=round(duration_s, 3),
                gpu_power_w=round(avg_power, 2),
                gpu_temp_c=round(gpu_after.get("gpu_temp_c", 0.0), 1),
                vram_used_mb=round(gpu_after.get("vram_used_mb", 0.0), 0),
                joules_per_token=j_per_tok,
                tco_usd=tco,
                judge_score=score,
                judge_reasoning=reasoning,
                judge_model=judge_model,
                rubric=p.get("rubric", ""),
            )

            _append_ledger(run)
            _watchdog_check(score, p["id"])
            runs.append(run)

            log.info(
                f"  Score={score}/5 | TTFT={ttft_ms:.0f}ms | "
                f"{tps:.1f}tok/s | {avg_power:.0f}W | J/tok={j_per_tok:.4f}"
            )

            # Cooldown between prompts to avoid thermal saturation
            await asyncio.sleep(2.0)

    return runs


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="[BKM-032] Silicon Benchmarking Harness")
    parser.add_argument("--tag", type=str, default=None, help="Filter prompts by tag")
    parser.add_argument("--id", type=str, default=None, help="Run a single prompt by ID")
    parser.add_argument(
        "--engine", type=str, default="vllm", choices=["vllm", "ollama"], help="Inference engine target"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without executing")
    parser.add_argument("--list-tags", action="store_true", help="Print available tags and exit")
    args = parser.parse_args()

    if args.list_tags:
        tags = sorted({t for p in EVAL_PROMPTS for t in p["tags"]})
        print("Available tags:", ", ".join(tags))
        return

    prompts = EVAL_PROMPTS
    if args.tag:
        prompts = [p for p in EVAL_PROMPTS if args.tag in p["tags"]]
        log.info(f"Filtered to {len(prompts)} prompts with tag '{args.tag}'")
    if args.id:
        prompts = [p for p in prompts if p["id"] == args.id]
        log.info(f"Running single prompt: {args.id}")

    if not prompts:
        log.error("No prompts matched. Use --list-tags to see available tags.")
        sys.exit(1)

    log.info(f"Starting benchmark: {len(prompts)} prompts | engine={args.engine} | dry_run={args.dry_run}")
    runs = asyncio.run(run_eval(prompts, engine=args.engine, dry_run=args.dry_run))

    if not args.dry_run:
        scored = [r for r in runs if r.judge_score > 0]
        avg_score = sum(r.judge_score for r in scored) / len(scored) if scored else 0
        avg_tps = sum(r.tokens_per_sec for r in runs) / len(runs) if runs else 0
        log.info(
            f"\n{'='*60}\n"
            f"BENCHMARK COMPLETE\n"
            f"  Prompts run:   {len(runs)}\n"
            f"  Avg judge:     {avg_score:.2f}/5\n"
            f"  Avg tok/s:     {avg_tps:.1f}\n"
            f"  Ledger:        {BENCHMARKS_LEDGER}\n"
            f"{'='*60}"
        )


if __name__ == "__main__":
    main()
