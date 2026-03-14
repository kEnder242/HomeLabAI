import os
import json
import logging
import random
import sys

# Path Self-Awareness
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_SELF_DIR)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Montana Protocol
from infra.montana import reclaim_logger
reclaim_logger("SentinelForge")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SENTINEL-FORGE] %(message)s')

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "sentinel_training_data.jsonl")

# Curriculum Seeds
SITUATIONS = [
    {"tag": "[GREETING]", "intent": "CASUAL", "domain": "standard", "hint": "Acknowledge the user warmly and wait for strategic depth."},
    {"tag": "[TECHNICAL_DEEP_DIVE]", "intent": "STRATEGIC", "domain": "exp_bkm", "hint": "The user is digging into architecture. Focus on BKM consistency."},
    {"tag": "[SILICON_FAILURE]", "intent": "STRATEGIC", "domain": "exp_tlm", "hint": "Hardware instability detected. Audit the telemetry logs immediately."},
    {"tag": "[EXIT_LIKELY]", "intent": "CASUAL", "domain": "standard", "hint": "The user is winding down. Suggest a graceful closure."},
    {"tag": "[FORENSIC_RECALL]", "intent": "STRATEGIC", "domain": "exp_for", "hint": "Digging into 18-year history. Connect the breadcrumbs across the years."},
]

QUERIES = [
    ("Hello lab, are we online?", "[GREETING]", "CASUAL", "standard"),
    ("What's the best way to handle a VRAM leak in vLLM?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "exp_bkm"),
    ("Check the 2022 logs for that PCIe error burst.", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    ("Why is the GPU temp at 85C?", "[SILICON_FAILURE]", "STRATEGIC", "exp_tlm"),
    ("Thanks, that's all for now.", "[EXIT_LIKELY]", "CASUAL", "standard"),
    ("Analyze the race condition in the 2008 RAID controller.", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    ("Narf! Can you see the status?", "[GREETING]", "CASUAL", "standard"),
    ("How does the Resonant Vibe architecture prevent logic drift?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "exp_bkm"),
]

def generate_data():
    dataset = []
    
    # 1. Generate from seeds
    for query, tag, intent, domain in QUERIES:
        # Find matching hint
        hint = "Proceed with caution."
        for s in SITUATIONS:
            if s["tag"] == tag:
                hint = s["hint"]
                break
        
        response = {
            "intent": intent,
            "domain": domain,
            "situation": tag,
            "hints": hint
        }
        
        # Format for Unsloth / Llama 3.1
        instruction = f"Analyze the user query for situational awareness: '{query}'"
        output = json.dumps(response)
        
        dataset.append({
            "instruction": instruction,
            "input": "",
            "output": output
        })

    # 2. Add some 'Sentient Sentinel' specific behaviors (BKM style)
    # This teaches the model the "Vibe" of the sentinel
    dataset.append({
        "instruction": "What is your primary mandate as the Lab Sentinel?",
        "input": "",
        "output": "My primary mandate is to overheard all bicameral interactions and provide dynamic VIBES and coordination HINTS. I ensure that data remains the bones, the LLM remains the muscle, and the flow that connects them remains the tendons."
    })

    with open(OUTPUT_FILE, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"Generated {len(dataset)} sentinel training pairs in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_data()
