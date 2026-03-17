#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FORGE-01: Curriculum Preparation (v1.1)
Transforms raw induction captures into instruction-tuning datasets for Unsloth.
"""

import json
import os
from pathlib import Path

# --- Absolute Paths ---
EXPERTISE_DIR = Path("/home/jallred/Dev_Lab/HomeLabAI/src/forge/expertise")
HISTORY_RAW = EXPERTISE_DIR / "bkm_master_manifest.jsonl"
VOICE_RAW = EXPERTISE_DIR / "cli_voice_dataset.jsonl"

HISTORY_OUT = EXPERTISE_DIR / "lab_history_training.jsonl"
VOICE_OUT = EXPERTISE_DIR / "cli_voice_training.jsonl"
SENTINEL_OUT = EXPERTISE_DIR / "lab_sentinel_training.jsonl"

def build_sentinel_dataset():
    """Generates the initial seed dataset for the Lab Sentinel."""
    print(f"Building Sentinel Dataset -> {SENTINEL_OUT}")
    # We'll just define the seeds here directly to avoid import complexity
    from forge.generate_sentinel_data import CURRICULUM, SITUATIONS
    
    dataset = []
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

    # Add Mandates
    dataset.extend([
        {"instruction": "What is your primary mandate as the Lab Sentinel?", "input": "", "output": "My primary mandate is to overhear all bicameral interactions and provide dynamic VIBES and coordination HINTS. I ensure that data remains the bones, the LLM remains the muscle, and the flow that connects them remains the tendons."},
        {"instruction": "Explain the Law of Semantic Indirection [BKM-015.1].", "input": "", "output": "The Law of Semantic Indirection states that the Hub must never use hardcoded keyword matching for orchestration. Instead, it must use the Sentinel to retrieve semantic vibes, ensuring the Lab's logic evolves as the technical archive deepens."}
    ])

    with open(SENTINEL_OUT, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
    print(f"✅ Sentinel Forge Ready: {len(dataset)} pairs.")

def build_history_dataset():
    print(f"Building History Dataset: {HISTORY_RAW} -> {HISTORY_OUT}")
    if not HISTORY_RAW.exists():
        print(f"❌ Error: {HISTORY_RAW} not found.")
        return
    count = 0
    with open(HISTORY_RAW, "r") as f_in, open(HISTORY_OUT, "w") as f_out:
        for line in f_in:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                # Field name in bkm_master_manifest is 'context'
                raw_txt = data.get("context") or data.get("raw_text") or data.get("raw_llm_output", "")
                if not raw_txt: continue
                
                entry = {
                    "instruction": f"Recall technical details regarding: {data.get('summary')}",
                    "input": "",
                    "output": raw_txt
                }
                f_out.write(json.dumps(entry) + "\n")
                count += 1
            except Exception as e:
                print(f"Error parsing line: {e}")
    print(f"✅ History Forge Ready: {count} pairs.")

def build_voice_dataset():
    print(f"Building Voice Dataset: {VOICE_RAW} -> {VOICE_OUT}")
    if not VOICE_RAW.exists():
        print(f"❌ Error: {VOICE_RAW} not found.")
        return
    count = 0
    with open(VOICE_RAW, "r") as f_in, open(HISTORY_OUT if HISTORY_RAW.exists() else VOICE_OUT, "w") as f_out: # wait, fixing typo
        pass # rewriting function for clarity

def build_voice_dataset_fixed():
    print(f"Building Voice Dataset: {VOICE_RAW} -> {VOICE_OUT}")
    if not VOICE_RAW.exists():
        print(f"❌ Error: {VOICE_RAW} not found.")
        return
    count = 0
    with open(VOICE_RAW, "r") as f_in, open(VOICE_OUT, "w") as f_out:
        for line in f_in:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                # Voice dataset is already in instruction/output format
                if "instruction" in data and "output" in data:
                    f_out.write(json.dumps(data) + "\n")
                    count += 1
                else:
                    output_txt = data.get("response") or data.get("text", "")
                    if output_txt:
                        entry = {
                            "instruction": data.get("prompt", "Facilitate technical dialogue."),
                            "input": "",
                            "output": output_txt
                        }
                        f_out.write(json.dumps(entry) + "\n")
                        count += 1
            except Exception as e:
                print(f"Error parsing line: {e}")
    print(f"✅ Voice Forge Ready: {count} pairs.")

if __name__ == "__main__":
    EXPERTISE_DIR.mkdir(parents=True, exist_ok=True)
    build_history_dataset()
    build_voice_dataset_fixed()
    build_sentinel_dataset()
