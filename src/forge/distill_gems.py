import os
import json
import glob
import logging
import sys

# Montana Protocol: Logger Reclamation
from infra.montana import reclaim_logger
reclaim_logger("DistillForge")

from infra.engine_client import query_sovereign_engine, resolve_active_deep_thought_target

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FORGE] %(message)s')

WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "training_data.jsonl")

DISTILL_PROMPT = """
You are the High-Fidelity Distillation Engine of Acme Lab.
TASK: Transform the following technical "Diamond Gem" into a high-density "Instruction-Response" pair for LoRA training.

GOAL: Capture the engineering pedigree, the specific technical solution, and the "Lead Engineer" tone (BKM Protocol).

TECHNICAL GEM:
{gem_json}

RULES:
1. Instruction: A specific, challenging question a Lead Engineer would ask about this topic.
2. Response: A dense, authoritative answer following the BKM Protocol (One-liners, Core Logic, specific trigger points).
3. DO NOT include conversational filler.
4. Format the output as a JSON object: {{"instruction": "...", "response": "..."}}
"""

def distill_gem(gem):
    prompt = DISTILL_PROMPT.format(gem_json=json.dumps(gem))
    try:
        res = query_sovereign_engine(
            prompt=prompt,
            system_prompt="You are the High-Fidelity Distillation Engine of Acme Lab.",
            json_mode=True,
            timeout=60.0
        )
        if isinstance(res, dict) and "instruction" in res and "response" in res:
            return res
        elif isinstance(res, str):
            try:
                parsed = json.loads(res)
                if isinstance(parsed, dict) and "instruction" in parsed and "response" in parsed:
                    return parsed
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Distillation failed: {e}")
    return None

def main(limit=None):
    active_seat = resolve_active_deep_thought_target()
    logging.info(f"Starting Distillation Pipeline. Target Engine Seat: {active_seat.get('name')} ({active_seat.get('host')}:{active_seat.get('port')})")
    
    gems = []
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    for jf in json_files:
        if any(x in jf for x in ["themes", "status", "queue", "state", "search_index", "pager_activity", "file_manifest"]): continue
        try:
            with open(jf, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for event in data:
                        if event.get('rank', 0) >= 4:
                            gems.append(event)
        except Exception: pass

    logging.info(f"Identified {len(gems)} Rank 4 gems.")
    
    if limit:
        gems = gems[:limit]
        logging.info(f"Limiting to first {limit} gems for test batch.")

    count = 0
    with open(TRAINING_DATA_PATH, "a") as f:
        for gem in gems:
            logging.info(f"Distilling: {gem.get('summary', 'Unknown')[:50]}...")
            pair = distill_gem(gem)
            if pair:
                f.write(json.dumps(pair) + "\n")
                count += 1
                logging.info(f"Successfully forged pair {count}/{len(gems)}")
            
    logging.info(f"Distillation complete. {count} pairs saved to {TRAINING_DATA_PATH}")

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=limit)
