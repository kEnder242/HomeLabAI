#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dream Voice (Stage 3: Persona Synthesis)
[FEAT-204] CLI Persona Induction

Uses the 4090 Sovereign to generate "Ideal Engineer Responses" 
for the refined prompts, creating an instruction-tuning dataset.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
import websockets

# --- Configuration ---
LOG_LEVEL = logging.INFO
EXPERTISE_DIR = Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise"
REFINED_PROMPTS = EXPERTISE_DIR / "refined_prompts.jsonl"
VOICE_DATASET = EXPERTISE_DIR / "cli_voice_dataset.jsonl"
SENTINEL_DATASET = EXPERTISE_DIR / "lab_sentinel_training.jsonl"
BRAIN_NODE_URI = "ws://localhost:8765"

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


async def generate_dream_response(websocket, prompt, mode="voice"):
    """Queries the Sovereign for the ideal 'Engineer Voice' or 'Sentinel Decision'."""
    if mode == "sentinel":
        dream_query = (
            "[ME] [SENTINEL_DREAM]: Analyze this user query: '{prompt}'. "
            "Should this be triaged to the high-latency Strategic Brain (RTX 4090) or handled by the low-latency Local Pinky (RTX 2080 Ti)? "
            "Output 'TRIAGE: BRAIN' if complex/strategic/coding, or 'TRIAGE: PINKY' if simple/conversational/status. "
            "Provide a one-sentence technical rationale."
        )
    else:
        # System hint to force the persona
        dream_query = (
            "[ME] [DREAM_PASS]: Act as the Lead Engineer. Provide a concise, professional, "
            f"and technically accurate response to this directive: '{prompt}'"
        )

    message = {"type": "text_input", "content": dream_query}
    await websocket.send(json.dumps(message))

    # Sovereign wait loop
    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < 120:
        try:
            resp = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(resp)
            source = data.get("brain_source", "")
            text = data.get("brain", "")

            # We want the deep derivation from the Brain
            if "brain" in source.lower():
                return text
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logging.error(f"Dream Error: {e}")
            break
    return None


async def main(limit=10, mode="voice", order="forward", duration_hours=None):
    """Main synthesis loop."""
    logging.info(f"Starting Dream Synthesis [Mode: {mode}, Limit: {limit}, Order: {order}]...")
    start_time_global = time.time()

    if not REFINED_PROMPTS.exists():
        logging.error("Refined prompts not found.")
        return

    EXPERTISE_DIR.mkdir(parents=True, exist_ok=True)
    
    target_file = SENTINEL_DATASET if mode == "sentinel" else VOICE_DATASET
    
    # [FEAT-204] Resume Logic: Load already dreamed prompts
    seen_prompts = set()
    if target_file.exists():
        with open(target_file, 'r') as f_check:
            for line in f_check:
                try:
                    instruction = json.loads(line).get('instruction')
                    if instruction:
                        seen_prompts.add(instruction)
                except Exception:
                    pass

    # [FEAT-296] Fast-Forward: Load and potentially reverse the queue
    with open(REFINED_PROMPTS, "r") as f_in:
        all_lines = f_in.readlines()
    
    if order == "reverse":
        logging.info("[ORDER] Reversing queue to process newest items first.")
        all_lines.reverse()

    count = 0
    async with websockets.connect(BRAIN_NODE_URI) as websocket:
        await websocket.recv()  # Greeting

        for line in all_lines:
            # Check constraints
            if count >= limit:
                logging.info(f"[LIMIT] Reached item limit ({limit}).")
                break
            
            if duration_hours:
                elapsed = (time.time() - start_time_global) / 3600
                if elapsed >= duration_hours:
                    logging.info(f"[TIME] Reached duration limit ({duration_hours}h).")
                    break

            entry = json.loads(line)
            prompt = entry.get("prompt")
            
            if prompt in seen_prompts:
                continue

            logging.info(f"Dreaming [{mode}] for: {prompt[:50]}...")
            ideal_response = await generate_dream_response(websocket, prompt, mode=mode)

            if ideal_response:
                dataset_entry = {
                    "instruction": prompt,
                    "input": "",
                    "output": ideal_response,
                }
                with open(target_file, "a") as f_out:
                    f_out.write(json.dumps(dataset_entry) + "\n")
                count += 1
                logging.info(f"Synthesized [{count}/{limit}]")

            await asyncio.sleep(2)  # Short cadence

    logging.info(f"Dream Synthesis [{mode}] Finished.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Acme Lab Dream Voice Synthesis")
    parser.add_argument("limit", type=int, default=10, help="Item limit")
    parser.add_argument("mode", default="voice", help="Synthesis mode (voice|sentinel)")
    parser.add_argument("--order", default="forward", choices=["forward", "reverse"], help="Queue order")
    parser.add_argument("--hours", type=float, default=None, help="Time limit in hours")
    
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, mode=args.mode, order=args.order, duration_hours=args.hours))
