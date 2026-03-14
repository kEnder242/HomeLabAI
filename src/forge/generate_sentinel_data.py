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

# --- Curriculum Seeds ---

SITUATIONS = [
    {"tag": "[GREETING]", "intent": "CASUAL", "domain": "standard", "hint": "Acknowledge the user warmly and wait for strategic depth."},
    {"tag": "[TECHNICAL_DEEP_DIVE]", "intent": "STRATEGIC", "domain": "exp_bkm", "hint": "The user is digging into architecture. Focus on BKM consistency."},
    {"tag": "[SILICON_FAILURE]", "intent": "STRATEGIC", "domain": "exp_tlm", "hint": "Hardware instability detected. Audit the telemetry logs immediately."},
    {"tag": "[EXIT_LIKELY]", "intent": "CASUAL", "domain": "standard", "hint": "The user is winding down. Suggest a graceful closure."},
    {"tag": "[FORENSIC_RECALL]", "intent": "STRATEGIC", "domain": "exp_for", "hint": "Digging into 18-year history. Connect the breadcrumbs across the years."},
    {"tag": "[CODE_AUDIT]", "intent": "STRATEGIC", "domain": "exp_bkm", "hint": "Analyze the technical logic for potential race conditions or regressions."},
    {"tag": "[STATUS_CHECK]", "intent": "CASUAL", "domain": "standard", "hint": "Provide a terse summary of physical health (VRAM/Loads)."},
    {"tag": "[AMBIGUOUS_INTENT]", "intent": "STRATEGIC", "domain": "standard", "hint": "Intent is unclear. Pinky should ask for clarification while Brain pre-warms."},
]

# (Query, Tag, Intent, Domain)
CURRICULUM = [
    # 1. Banter & Greetings
    ("Hello lab, are we online?", "[GREETING]", "CASUAL", "standard"),
    ("Narf! Can you see the status?", "[GREETING]", "CASUAL", "standard"),
    ("Poit! Just checking in.", "[GREETING]", "CASUAL", "standard"),
    
    # 2. Telemetry & Hardware
    ("Why is the GPU temp at 85C?", "[SILICON_FAILURE]", "STRATEGIC", "exp_tlm"),
    ("Check the VRAM usage on the 2080 Ti.", "[STATUS_CHECK]", "CASUAL", "standard"),
    ("Report the latest RAPL energy metrics.", "[STATUS_CHECK]", "CASUAL", "standard"),
    ("Is the vLLM engine thermal-throttling?", "[SILICON_FAILURE]", "STRATEGIC", "exp_tlm"),
    
    # 3. Architecture & BKMs
    ("What's the best way to handle a VRAM leak in vLLM?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "exp_bkm"),
    ("How does the Resonant Vibe architecture prevent logic drift?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "exp_bkm"),
    ("Explain the Class 1 design philosophy.", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "exp_bkm"),
    ("Validate the logic in acme_lab.py for race conditions.", "[CODE_AUDIT]", "STRATEGIC", "exp_bkm"),
    
    # 4. Forensics & History
    ("Check the 2022 logs for that PCIe error burst.", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    ("Analyze the race condition in the 2008 RAID controller.", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    ("What was the outcome of the 2015 performance review?", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    ("Search for 'VISA' debug notes in the 2011 archive.", "[FORENSIC_RECALL]", "STRATEGIC", "exp_for"),
    
    # 5. Exit Sentiment
    ("Thanks, that's all for now.", "[EXIT_LIKELY]", "CASUAL", "standard"),
    ("Okay, goodbye.", "[EXIT_LIKELY]", "CASUAL", "standard"),
    ("I'm done for the night.", "[EXIT_LIKELY]", "CASUAL", "standard"),
    
    # 6. Ambiguous / Complex
    ("I think something is wrong with the tendons.", "[AMBIGUOUS_INTENT]", "STRATEGIC", "standard"),
    ("The mind is feeling hollow today.", "[AMBIGUOUS_INTENT]", "STRATEGIC", "standard"),
]

def generate_data():
    dataset = []
    
    # 1. Triage Patterns
    for query, tag, intent, domain in CURRICULUM:
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
        
        dataset.append({
            "instruction": f"Analyze the user query for situational awareness: '{query}'",
            "input": "",
            "output": json.dumps(response)
        })

    # 2. Identity & Mandates (BKM style)
    dataset.extend([
        {
            "instruction": "What is your primary mandate as the Lab Sentinel?",
            "input": "",
            "output": "My primary mandate is to overhear all bicameral interactions and provide dynamic VIBES and coordination HINTS. I ensure that data remains the bones, the LLM remains the muscle, and the flow that connects them remains the tendons."
        },
        {
            "instruction": "Explain the Law of Semantic Indirection [BKM-015.1].",
            "input": "",
            "output": "The Law of Semantic Indirection states that the Hub must never use hardcoded keyword matching for orchestration. Instead, it must use the Sentinel to retrieve semantic vibes, ensuring the Lab's logic evolves as the technical archive deepens."
        },
        {
            "instruction": "How do you handle high VRAM pressure in the Resonant Vibe architecture?",
            "input": "",
            "output": "I trigger the Resilience Ladder. At >9500MiB, I downshift to the LARGE tier (1.5B). At >11000MiB, I execute a CRITICAL Hard Stop to preserve silicon integrity."
        }
    ])

    with open(OUTPUT_FILE, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"Generated {len(dataset)} high-fidelity sentinel training pairs in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_data()
