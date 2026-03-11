import os
import json
import requests
import glob
import logging
import sys

# Montana Protocol: Logger Reclamation
from infra.montana import reclaim_logger
reclaim_logger("DistillForge")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [FORGE] %(message)s')

WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
TRAINING_DATA_PATH = os.path.join(os.path.dirname(__file__), "training_data.jsonl")
INFRA_CONFIG = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")

def get_brain_url():
    try:
        with open(INFRA_CONFIG, "r") as f:
            infra = json.load(f)
        primary = infra.get("nodes", {}).get("brain", {}).get("primary", "KENDER")
        host_cfg = infra.get("hosts", {}).get(primary, {})
        ip = host_cfg.get("ip_hint", "192.168.1.26")
        port = host_cfg.get("ollama_port", 11434)
        return f"http://{ip}:{port}/api/chat"
    except Exception as e:
        logging.error(f"Failed to resolve Brain URL: {e}")
        return "http://192.168.1.26:11434/api/chat"

BRAIN_URL = get_brain_url()

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
    payload = {
        "model": "llama3:latest",
        "messages": [{"role": "user", "content": DISTILL_PROMPT.format(gem_json=json.dumps(gem))}],
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(BRAIN_URL, json=payload, timeout=60)
        if response.status_code == 200:
            content = response.json().get("message", {}).get("content", "")
            return json.loads(content)
        else:
            logging.error(f"Brain error: {response.status_code}")
    except Exception as e:
        logging.error(f"Distillation failed: {e}")
    return None

def main(limit=None):
    logging.info(f"Starting Distillation Pipeline. Target: {BRAIN_URL}")
    
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
