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
    {"tag": "[GREETING]", "intent": "CASUAL", "topic": "Casual", "domain": "standard", "casual": 0.9, "intrigue": 0.1, "importance": 0.1, "hint": "Acknowledge the user warmly and wait for strategic depth."},
    {"tag": "[TECHNICAL_DEEP_DIVE]", "intent": "STRATEGIC", "topic": "Code", "domain": "exp_bkm", "casual": 0.1, "intrigue": 0.7, "importance": 0.6, "hint": "The user is digging into architecture. Focus on BKM consistency."},
    {"tag": "[SILICON_FAILURE]", "intent": "STRATEGIC", "topic": "Silicon", "domain": "exp_tlm", "casual": 0.0, "intrigue": 0.9, "importance": 0.9, "hint": "Hardware instability detected. Audit the telemetry logs immediately."},
    {"tag": "[EXIT_LIKELY]", "intent": "CASUAL", "topic": "Casual", "domain": "standard", "casual": 0.8, "intrigue": 0.1, "importance": 0.1, "hint": "The user is winding down. Suggest a graceful closure."},
    {"tag": "[FORENSIC_RECALL]", "intent": "STRATEGIC", "topic": "Historical", "domain": "exp_for", "casual": 0.1, "intrigue": 0.8, "importance": 0.7, "hint": "Digging into 18-year history. Connect the breadcrumbs across the years."},
    {"tag": "[CODE_AUDIT]", "intent": "STRATEGIC", "topic": "Code", "domain": "exp_bkm", "casual": 0.1, "intrigue": 0.8, "importance": 0.7, "hint": "Analyze the technical logic for potential race conditions or regressions."},
    {"tag": "[STATUS_CHECK]", "intent": "CASUAL", "topic": "Silicon", "domain": "standard", "casual": 0.4, "intrigue": 0.3, "importance": 0.3, "hint": "Provide a terse summary of physical health (VRAM/Loads)."},
    {"tag": "[AMBIGUOUS_INTENT]", "intent": "STRATEGIC", "topic": "Meta", "domain": "standard", "casual": 0.3, "intrigue": 0.6, "importance": 0.4, "hint": "Intent is unclear. Pinky should ask for clarification while Brain pre-warms."},
    {"tag": "[OPERATIONAL_RESTART]", "intent": "OPERATIONAL", "topic": "Meta", "domain": "standard", "casual": 0.1, "intrigue": 0.9, "importance": 0.9, "hint": "System command detected. Execute shortcut immediately."},
    {"tag": "[CORRECTIVE_BIAS]", "intent": "STRATEGIC", "topic": "Meta", "domain": "exp_for", "casual": 0.0, "intrigue": 0.9, "importance": 1.0, "hint": "Human is correcting the system. Maximum fidelity required."},
]

# (Query, Tag, Intent, Topic, Domain, Casual, Intrigue, Importance)
CURRICULUM = [
    # 1. Banter & Greetings
    ("Hello lab, are we online?", "[GREETING]", "CASUAL", "Casual", "standard", 0.9, 0.1, 0.1),
    ("Narf! Can you see the status?", "[GREETING]", "CASUAL", "Casual", "standard", 0.9, 0.2, 0.1),
    ("Poit! Just checking in.", "[GREETING]", "CASUAL", "Casual", "standard", 0.9, 0.1, 0.1),
    
    # 2. Telemetry & Hardware
    ("Why is the GPU temp at 85C?", "[SILICON_FAILURE]", "STRATEGIC", "Silicon", "exp_tlm", 0.0, 0.9, 0.9),
    ("Check the VRAM usage on the 2080 Ti.", "[STATUS_CHECK]", "CASUAL", "Silicon", "standard", 0.5, 0.3, 0.3),
    ("Report the latest RAPL energy metrics.", "[STATUS_CHECK]", "CASUAL", "Silicon", "standard", 0.4, 0.4, 0.3),
    ("Is the vLLM engine thermal-throttling?", "[SILICON_FAILURE]", "STRATEGIC", "Silicon", "exp_tlm", 0.1, 0.8, 0.8),
    
    # 3. Architecture & BKMs
    ("What's the best way to handle a VRAM leak in vLLM?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "Code", "exp_bkm", 0.1, 0.7, 0.6),
    ("How does the Resonant Vibe architecture prevent logic drift?", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "Meta", "exp_bkm", 0.1, 0.9, 0.7),
    ("Explain the Class 1 design philosophy.", "[TECHNICAL_DEEP_DIVE]", "STRATEGIC", "Meta", "exp_bkm", 0.2, 0.8, 0.6),
    ("Validate the logic in acme_lab.py for race conditions.", "[CODE_AUDIT]", "STRATEGIC", "Code", "exp_bkm", 0.0, 0.9, 0.8),
    
    # 4. Forensics & History
    ("Check the 2022 logs for that PCIe error burst.", "[FORENSIC_RECALL]", "STRATEGIC", "Historical", "exp_for", 0.1, 0.8, 0.7),
    ("Analyze the race condition in the 2008 RAID controller.", "[FORENSIC_RECALL]", "STRATEGIC", "Historical", "exp_for", 0.0, 0.9, 0.8),
    ("What was the outcome of the 2015 performance review?", "[FORENSIC_RECALL]", "STRATEGIC", "Historical", "exp_for", 0.2, 0.7, 0.6),
    ("Search for 'VISA' debug notes in the 2011 archive.", "[FORENSIC_RECALL]", "STRATEGIC", "Historical", "exp_for", 0.1, 0.8, 0.7),
    
    # 5. Exit Sentiment
    ("Thanks, that's all for now.", "[EXIT_LIKELY]", "CASUAL", "Casual", "standard", 0.9, 0.1, 0.1),
    ("Okay, goodbye.", "[EXIT_LIKELY]", "CASUAL", "Casual", "standard", 0.9, 0.1, 0.1),
    ("I'm done for the night.", "[EXIT_LIKELY]", "CASUAL", "Casual", "standard", 0.9, 0.1, 0.1),
    
    # 6. Operational
    ("Restart the lab node.", "[OPERATIONAL_RESTART]", "OPERATIONAL", "Meta", "standard", 0.1, 0.9, 0.9),
    ("Neuralyzer.", "[OPERATIONAL_RESTART]", "OPERATIONAL", "Meta", "standard", 0.2, 0.9, 0.9),
    ("Close the lab.", "[OPERATIONAL_RESTART]", "OPERATIONAL", "Meta", "standard", 0.1, 1.0, 1.0),

    # 7. Corrective Bias
    ("No, that's wrong. Re-read the BKM.", "[CORRECTIVE_BIAS]", "STRATEGIC", "Meta", "exp_for", 0.0, 0.9, 1.0),
    ("Actually, the 2080 Ti is a Turing card, not Pascal.", "[CORRECTIVE_BIAS]", "STRATEGIC", "Silicon", "exp_for", 0.0, 0.8, 1.0),
]

def generate_data():
    dataset = []
    
    # 1. Triage Patterns
    for query, tag, intent, topic, domain, casual, intrigue, importance in CURRICULUM:
        hint = "Proceed with caution."
        for s in SITUATIONS:
            if s["tag"] == tag:
                hint = s["hint"]
                break
        
        response = {
            "intent": intent,
            "topic": topic,
            "domain": domain,
            "casual": casual,
            "intrigue": intrigue,
            "importance": importance,
            "situation": tag,
            "hints": hint
        }
        
        # Aligned with lab_node.py prompting style
        instruction = f"ROLE: Situational Auditor.\nTASK: Analyze the query and provide a high-fidelity scalar triage.\nAnalyze: {query}"
        
        dataset.append({
            "instruction": instruction,
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
        }
    ])

    with open(OUTPUT_FILE, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"Generated {len(dataset)} high-fidelity sentinel training pairs in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_data()
