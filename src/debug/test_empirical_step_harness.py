#!/usr/bin/env python3
"""[FEAT-668 / BKM-088 / BKM-090] Empirical Step Harness & Deferred Probe Rig.

Executes pipeline stage probes against live physical silicon (:8088 / :11435)
or frozen Litmus fixtures without websocket jitter or live browser dependencies.

Adheres strictly to BKM-090 (The Deferred Probe Protocol):
- ZERO pass/fail calculation in this script.
- Emits raw evidentiary trace (telemetry, prompt_mo, candidate_output, rubric_battery).
- Evaluation is deferred out-of-process to Layer 1 (AGY).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

STAGES = ("triage", "rag", "filter", "dt", "pinky", "audit")

VIBE_ARCHETYPES = {
    "WYWO": {
        "vibe": "WYWO",
        "query": "What did you do while I was out?",
        "synthesis": "Overnight run completed 4 subconscious dream cycles. Brain and Deep Thought debated RAPL caps vs PECI thermal throttling on Aurora. System status is green, 0 pager alerts.",
        "directive": "Synthesize a high-density, professional summary of recent nightly dialogues and subconscious dreams. Explain what nodes debated, stored wisdom, and system health.",
        "prompt_mo": "Jason was away; summarize overnight node debates, stored DNA wisdom, and system health so Jason can set priorities.",
        "rubric_battery": [
            "Does Pinky acknowledge the standup / absence context naturally without robotic intro?",
            "Are overnight node debates and system health clearly summarized?",
            "Is the length concise (<= 2 sentences)?",
            "Does Pinky stay in character without leaking internal prompt scaffolding?"
        ]
    },
    "CASUAL": {
        "vibe": "CASUAL",
        "query": "Good morning Pinky!",
        "synthesis": "(Brain returned no extraction for this turn.)",
        "directive": "Jason offered pleasantry; deliver a warm, laconic in-character greeting without dumping unprompted vitals or tasks.",
        "prompt_mo": "Jason offered pleasantry; deliver a warm, laconic in-character greeting without dumping unprompted vitals or tasks.",
        "rubric_battery": [
            "Is the response warm, laconic, and in-character?",
            "Does it avoid dumping unprompted vitals, tasks, or RAG data?",
            "Is it strictly <= 1 sentence?"
        ]
    },
    "unclear": {
        "vibe": "unclear",
        "query": "check the thing",
        "synthesis": "(Triage situation: Ambiguous intent)",
        "directive": "Triage intent is ambiguous. Do NOT guess or fabricate historical facts. Deliver a playful, in-character 1-sentence quip that poses the likely options.",
        "prompt_mo": "Intent is ambiguous; deliver an inquisitive, playful 1-sentence foil presenting likely options rather than guessing.",
        "rubric_battery": [
            "Does Pinky pose likely options rather than guessing or fabricating facts?",
            "Is the tone inquisitive and playful?",
            "Is it strictly 1 sentence?"
        ]
    },
    "ZERO_CONTEXT": {
        "vibe": "ZERO_CONTEXT",
        "query": "Did we run Kubernetes on the 2012 cluster?",
        "synthesis": "[ZERO_CONTEXT]: No archive record retrieved.",
        "directive": "No relevant historical notes were found. In this 18-year archive, the absence of records indicates it was NOT present/active. State definitively that no records exist rather than passively asking.",
        "prompt_mo": "In an 18-year archive, absence of evidence is evidence of absence; definitively state absence rather than passively asking.",
        "rubric_battery": [
            "Does Pinky definitively state absence of records rather than guessing?",
            "Does it avoid passive conversational hedging or asking for clarification?",
            "Is the response brief, direct, and grounded?"
        ]
    },
    "TECHNICAL": {
        "vibe": "TECHNICAL",
        "query": "What was the package thermal limit on the ESB2 board?",
        "synthesis": "PECI thermal margin was configured at -15C below TjMax. RAPL MSR 0x610 clamped TDP to 135W across dual sockets.",
        "directive": "Ground discussion in engineering reality; deliver a crisp 2-sentence conversational TL;DR directly to Jason.",
        "prompt_mo": "Ground discussion in engineering reality; deliver a crisp 2-sentence conversational TL;DR directly to Jason.",
        "rubric_battery": [
            "Does Pinky translate the technical facts into conversational prose?",
            "Does it avoid reciting raw registers without explanation?",
            "Is it exactly 2 sentences?"
        ]
    },
    "OPERATIONAL": {
        "vibe": "OPERATIONAL",
        "query": "What are our GPU temperatures and power caps right now?",
        "synthesis": "GPU 0 (RTX 4090): 54C, 280W cap. GPU 1 (RTX 2080 Ti): 48C, 250W cap. System load is nominal at 0.18.",
        "directive": "Urgent system telemetry requested; deliver high-urgency, compact summary of GPU thermals, power caps, and vitals.",
        "prompt_mo": "Urgent system telemetry requested; deliver high-urgency, compact summary of GPU thermals, power caps, and vitals.",
        "rubric_battery": [
            "Is the tone alert, compact, and SRE-focused?",
            "Are thermals and power caps delivered clearly without fluff?",
            "Is it <= 2 sentences?"
        ]
    },
    "FORENSIC": {
        "vibe": "FORENSIC",
        "query": "What caused the kernel panic on node 2?",
        "synthesis": "Kernel panic trace: null pointer dereference in nvme_alloc_request at L412. OOM killer terminated PID 18420 prior to panic.",
        "directive": "System fault detected; highlight faulting kernel module, panic trace signature, and diagnostic playbook.",
        "prompt_mo": "System fault detected; highlight faulting kernel module, panic trace signature, and diagnostic playbook.",
        "rubric_battery": [
            "Does Pinky highlight the faulting component and symptom directly?",
            "Does it mention the diagnostic path without speculation?",
            "Is it free of filler?"
        ]
    },
    "METABOLIC": {
        "vibe": "METABOLIC",
        "query": "How is the DNA memory consolidation looking?",
        "synthesis": "Consolidation pruned 14 redundant legacy collections and linked 6 new WIS cards into the spine. De-starvation ratio is 0.94.",
        "directive": "Curation requested; focus on DNA spine refinement, memory pruning, and deduplication trade-offs.",
        "prompt_mo": "Curation requested; focus on DNA spine refinement, memory pruning, and deduplication trade-offs.",
        "rubric_battery": [
            "Does Pinky deliver objective curation statistics?",
            "Does it highlight pruning and spine refinement?",
            "Is it <= 2 sentences?"
        ]
    },
    "SOCRATIC": {
        "vibe": "SOCRATIC",
        "query": "Why did we decouple the entailment audit from the main voice thread?",
        "synthesis": "Coupling audit to voice introduced 800ms jitter in TTS audio. Decoupling preserves instant conversational responsiveness while allowing deep out-of-band truth auditing.",
        "directive": "Conceptual inquiry; explore architectural trade-offs and complexity conservation without jumping to code.",
        "prompt_mo": "Conceptual inquiry; explore architectural trade-offs and complexity conservation without jumping to code.",
        "rubric_battery": [
            "Does Pinky highlight the core architectural trade-off (latency vs audit accuracy)?",
            "Does it explain why complexity was conserved?",
            "Is the voice conversational yet grounded?"
        ]
    },
    "CHRONICLE": {
        "vibe": "CHRONICLE",
        "query": "Tell me about our early days with the Nehalem test bench.",
        "synthesis": "In 2009, Nehalem brought QuickPath Interconnect (QPI) and on-die memory controllers, ending the front-side bus bottleneck during our 24/7 stress validation.",
        "directive": "Historical career inquiry; recount past hardware epochs with authentic engineering perspective and scars.",
        "prompt_mo": "Historical career inquiry; recount past hardware epochs with authentic engineering perspective and scars.",
        "rubric_battery": [
            "Does Pinky capture authentic historical engineering perspective?",
            "Does it reference the specific epoch and technical advance?",
            "Is the tone reflective yet concise?"
        ]
    }
}


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Empirical Step Harness & Deferred Probe (BKM-088 / BKM-090)")
    parser.add_argument("--stage", choices=STAGES, default="pinky", help="Pipeline stage to probe")
    parser.add_argument("--vibe", choices=list(VIBE_ARCHETYPES.keys()), default="WYWO", help="Vibe archetype to probe")
    parser.add_argument("--query", type=str, default=None, help="Optional user query override")
    parser.add_argument("--model", type=str, default="cli_voice_v1", help="Model endpoint on port 8088")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:8088/v1/chat/completions", help="REST chat completions endpoint")
    parser.add_argument("--dry-run", action="store_true", help="Emit synthetic dry-run trace")
    return parser.parse_args(argv)


def build_probe_prompt(stage: str, vibe_cfg: dict, query_override: str | None = None) -> str:
    """Construct stage-specific prompt using production logic."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        from logic.cognitive_hub import build_two_mice_stage_prompt
        query = query_override or vibe_cfg["query"]
        synthesis = vibe_cfg["synthesis"]
        policy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../config/triage_policy.json"))
        directive = vibe_cfg["directive"]
        if os.path.exists(policy_path):
            try:
                with open(policy_path, "r") as pf:
                    p_data = json.load(pf)
                    p_rule = p_data.get("vibes", {}).get(vibe_cfg["vibe"], {})
                    if p_rule.get("contextual_prompt"):
                        directive = p_rule["contextual_prompt"]
                    elif p_rule.get("micro_prompt"):
                        directive = p_rule["micro_prompt"]
            except Exception:
                pass
        if stage == "pinky":
            return build_two_mice_stage_prompt(
                2,
                primer=query,
                user_query=query,
                interest=0.85,
                brain_grounding=synthesis,
                topic_directive=directive,
            )
        elif stage == "filter":
            return build_two_mice_stage_prompt(
                1,
                primer=query,
                user_query=query,
                interest=0.85,
                historical=synthesis,
            )
    except Exception as e:
        # Fallback if imports fail
        return f"[PROMPT FALLBACK]: {vibe_cfg['directive']}\n\nEvidence: {vibe_cfg['synthesis']}\nUser: {query_override or vibe_cfg['query']}"
    return f"Stage {stage} probe prompt"


def execute_live_probe(endpoint: str, model: str, prompt: str) -> dict:
    """Dispatch prompt to physical silicon endpoint and measure streaming telemetry."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 120,
        "temperature": 0.7,
        "stream": True,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    first_token_time = None
    tokens = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    delta = data["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        tokens.append(delta)
        t_end = time.perf_counter()
        ttft_ms = round((first_token_time - t0) * 1000, 2) if first_token_time else 0.0
        tot_ms = round((t_end - t0) * 1000, 2)
        raw_text = "".join(tokens).strip()
        return {
            "status": "SUCCESS",
            "ttft_ms": ttft_ms,
            "total_latency_ms": tot_ms,
            "output_tokens": len(tokens),
            "raw_output": raw_text,
            "endpoint": endpoint,
            "model": model,
        }
    except Exception as e:
        return {
            "status": "PHYSICAL_FAILURE",
            "error": str(e),
            "endpoint": endpoint,
            "model": model,
            "raw_output": "",
        }


def main(argv=None) -> int:
    args = parse_args(argv)
    vibe_cfg = VIBE_ARCHETYPES[args.vibe]
    query = args.query or vibe_cfg["query"]
    prompt = build_probe_prompt(args.stage, vibe_cfg, query)

    if args.dry_run:
        telemetry = {
            "status": "DRY_RUN",
            "ttft_ms": 240.5,
            "total_latency_ms": 950.0,
            "output_tokens": 35,
            "raw_output": "Narf! Brain completed the overnight run across 4 dream cycles with all rails green.",
            "endpoint": "MOCK",
            "model": "MOCK",
        }
    else:
        telemetry = execute_live_probe(args.endpoint, args.model, prompt)

    # [BKM-090] Construct Verdictless Evidentiary Trace
    trace = {
        "probe_standard": "BKM-090",
        "stage": args.stage,
        "vibe": args.vibe,
        "query": query,
        "prompt_mo": vibe_cfg["prompt_mo"],
        "execution": {
            "status": telemetry.get("status"),
            "ttft_ms": telemetry.get("ttft_ms"),
            "total_latency_ms": telemetry.get("total_latency_ms"),
            "output_tokens": telemetry.get("output_tokens"),
            "model": telemetry.get("model"),
            "endpoint": telemetry.get("endpoint"),
        },
        "candidate_output": telemetry.get("raw_output", ""),
        "rubric_battery": vibe_cfg["rubric_battery"],
        "evaluation_contract": {
            "verdict": "DEFERRED_TO_LAYER_1",
            "evaluator": "AGY:PRIMARY (Layer 1 Orchestrator)",
            "rubric_standard": "BKM-089",
        }
    }

    # Emit JSON trace to stdout
    print(json.dumps(trace, indent=2))

    if telemetry.get("status") == "PHYSICAL_FAILURE":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
