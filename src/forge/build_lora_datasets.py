#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
[FEAT-160] / [FEAT-204] / [FEAT-246] / [BKM-055]
FORGE-01: Multi-Curriculum Dataset Blender & Master Curriculum Preparer
Assembles master_forge_curriculum.jsonl from curated foundations:
  - 40% User Voice & Directives (cli_voice_training.jsonl) [FEAT-204]
  - 35% Engineering Pedigree & BKMs (lab_history_training.jsonl) [FEAT-160]
  - 15% Sentinel Vibe & Triage (lab_sentinel_training.jsonl) [FEAT-246]
  - 10% Curated Rank 4 Gems (training_data.jsonl / distilled gems)
"""

import json
import os
import random
from pathlib import Path
from typing import Optional, Dict, List, Any

# --- Absolute Paths ---
EXPERTISE_DIR = Path("/home/jallred/Dev_Lab/HomeLabAI/src/forge/expertise")
HISTORY_RAW = EXPERTISE_DIR / "bkm_master_manifest.jsonl"
VOICE_RAW = EXPERTISE_DIR / "cli_voice_dataset.jsonl"

HISTORY_OUT = EXPERTISE_DIR / "lab_history_training.jsonl"
VOICE_OUT = EXPERTISE_DIR / "cli_voice_training.jsonl"
SENTINEL_OUT = EXPERTISE_DIR / "lab_sentinel_training.jsonl"
GEMS_OUT = Path("/home/jallred/Dev_Lab/HomeLabAI/src/forge/training_data.jsonl")

MASTER_CURRICULUM_OUT = EXPERTISE_DIR / "master_forge_curriculum.jsonl"

CURRICULUM_DISTRIBUTION = {
    "voice": 0.40,
    "pedigree": 0.35,
    "sentinel": 0.15,
    "gems": 0.10
}


def build_sentinel_dataset():
    """Generates the seed dataset for the Lab Sentinel."""
    print(f"Building Sentinel Dataset -> {SENTINEL_OUT}")
    try:
        from forge.generate_sentinel_data import CURRICULUM, SITUATIONS
    except ImportError:
        try:
            from src.forge.generate_sentinel_data import CURRICULUM, SITUATIONS
        except ImportError:
            CURRICULUM = []
            SITUATIONS = []

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

    with open(SENTINEL_OUT, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
    print(f"✅ Sentinel Forge Ready: {len(dataset)} pairs.")
    return len(dataset)


def build_history_dataset():
    """Extracts BKM and lab history records into standard instruction-response pairs."""
    print(f"Building History Dataset: {HISTORY_RAW} -> {HISTORY_OUT}")
    if not HISTORY_RAW.exists():
        print(f"❌ Error: {HISTORY_RAW} not found.")
        return 0
    count = 0
    with open(HISTORY_RAW, "r") as f_in, open(HISTORY_OUT, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                raw_txt = data.get("context") or data.get("raw_text") or data.get("raw_llm_output", "")
                if not raw_txt:
                    continue

                entry = {
                    "instruction": f"Recall technical details regarding: {data.get('summary', 'Engineering Concept')}",
                    "input": "",
                    "output": raw_txt
                }
                f_out.write(json.dumps(entry) + "\n")
                count += 1
            except Exception as e:
                print(f"Error parsing history line: {e}")
    print(f"✅ History Forge Ready: {count} pairs.")
    return count


def build_voice_dataset():
    """Extracts user voice prompts and directives into standard instruction-response pairs."""
    print(f"Building Voice Dataset: {VOICE_RAW} -> {VOICE_OUT}")
    if not VOICE_RAW.exists():
        print(f"❌ Error: {VOICE_RAW} not found.")
        return 0
    count = 0
    with open(VOICE_RAW, "r") as f_in, open(VOICE_OUT, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if "instruction" in data and "output" in data:
                    f_out.write(json.dumps(data) + "\n")
                    count += 1
                elif "prompt" in data and ("response" in data or "text" in data):
                    output_txt = data.get("response") or data.get("text", "")
                    if output_txt:
                        entry = {
                            "instruction": data.get("prompt"),
                            "input": "",
                            "output": output_txt
                        }
                        f_out.write(json.dumps(entry) + "\n")
                        count += 1
            except Exception as e:
                print(f"Error parsing voice line: {e}")
    print(f"✅ Voice Forge Ready: {count} pairs.")
    return count


def _load_jsonl_dataset(path: Path) -> list:
    """Helper to load and validate instruction/output pairs from a JSONL file."""
    if not path.exists():
        return []
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                instr = entry.get("instruction") or entry.get("prompt")
                out = entry.get("output") or entry.get("response") or entry.get("text")
                if instr and out:
                    records.append({
                        "instruction": str(instr).strip(),
                        "input": entry.get("input", ""),
                        "output": str(out).strip()
                    })
            except Exception:
                continue
    return records


def build_master_curriculum(output_path: Optional[Path] = None, target_size: int = 1000, seed: int = 3407) -> Path:
    """
    [FEAT-160] / [Story 83.1]
    Assembles master_forge_curriculum.jsonl with strict curriculum ratios:
      - 40% User Voice & Cadence
      - 35% Engineering Pedigree & BKMs
      - 15% Sentinel Vibe & Triage
      - 10% Curated Rank 4 Pearls
    """
    print("\n--- Assembling Multi-Curriculum Master Forge Dataset ---")
    random.seed(seed)
    dest_path = Path(output_path) if output_path else MASTER_CURRICULUM_OUT

    voice_items = _load_jsonl_dataset(VOICE_OUT)
    history_items = _load_jsonl_dataset(HISTORY_OUT)
    sentinel_items = _load_jsonl_dataset(SENTINEL_OUT)
    gems_items = _load_jsonl_dataset(GEMS_OUT)

    print(f"Pool sizes: Voice={len(voice_items)}, History={len(history_items)}, Sentinel={len(sentinel_items)}, Gems={len(gems_items)}")

    target_voice = int(target_size * CURRICULUM_DISTRIBUTION["voice"])
    target_history = int(target_size * CURRICULUM_DISTRIBUTION["pedigree"])
    target_sentinel = int(target_size * CURRICULUM_DISTRIBUTION["sentinel"])
    target_gems = target_size - (target_voice + target_history + target_sentinel)

    def sample_or_upsample(pool: list, target_count: int, label: str) -> list:
        if not pool:
            print(f"⚠️ Warning: Pool '{label}' is empty! Skipping.")
            return []
        stream_key = "pedigree" if label.lower() == "history" else label.lower()
        if len(pool) >= target_count:
            chosen = random.sample(pool, target_count)
        else:
            print(f"ℹ️ Upsampling '{label}' from {len(pool)} to {target_count} items.")
            chosen = [random.choice(pool) for _ in range(target_count)]
        return [{**item, "stream": stream_key} for item in chosen]

    curriculum = []
    curriculum.extend(sample_or_upsample(voice_items, target_voice, "Voice"))
    curriculum.extend(sample_or_upsample(history_items, target_history, "History"))
    curriculum.extend(sample_or_upsample(sentinel_items, target_sentinel, "Sentinel"))
    curriculum.extend(sample_or_upsample(gems_items, target_gems, "Gems"))

    # Shuffle combined dataset to interleave concepts
    random.shuffle(curriculum)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w") as f:
        for item in curriculum:
            f.write(json.dumps(item) + "\n")

    print(f"✅ Master Forge Curriculum Ready: {len(curriculum)} pairs -> {dest_path}\n")
    return dest_path


if __name__ == "__main__":
    EXPERTISE_DIR.mkdir(parents=True, exist_ok=True)
    build_history_dataset()
    build_voice_dataset()
    build_sentinel_dataset()
    build_master_curriculum(target_size=1000)
