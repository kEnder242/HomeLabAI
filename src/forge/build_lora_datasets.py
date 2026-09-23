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
DEV_LAB = Path("/home/jallred/Dev_Lab")
DNA_DIR = DEV_LAB / "Portfolio_Dev" / "dna"
PHILOSOPHY_JSON = DNA_DIR / "philosophy_data.json"
WISDOM_JSON = DNA_DIR / "wisdom_data.json"
RDNA_JSON = DNA_DIR / "rdna_questions.json"
PROTOCOLS_MD = DEV_LAB / "HomeLabAI" / "docs" / "Protocols.md"
FEATURES_MD = DEV_LAB / "Portfolio_Dev" / "FeatureTracker.md"

HISTORY_RAW = EXPERTISE_DIR / "bkm_master_manifest.jsonl"
VOICE_RAW = EXPERTISE_DIR / "cli_voice_dataset.jsonl"

HISTORY_OUT = EXPERTISE_DIR / "lab_history_training.jsonl"
VOICE_OUT = EXPERTISE_DIR / "cli_voice_training.jsonl"
SENTINEL_OUT = EXPERTISE_DIR / "lab_sentinel_training.jsonl"
DNA_OUT = EXPERTISE_DIR / "dna_polymorphic_training.jsonl"
GEMS_OUT = Path("/home/jallred/Dev_Lab/HomeLabAI/src/forge/training_data.jsonl")

MASTER_CURRICULUM_OUT = EXPERTISE_DIR / "master_forge_curriculum.jsonl"

CURRICULUM_DISTRIBUTION = {
    "voice": 0.30,
    "pedigree": 0.25,
    "dna": 0.25,
    "sentinel": 0.10,
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


def _build_dna_synthesis_index() -> Dict[str, str]:
    """
    [Story 865] Builds a {card_id -> narrative_context} index from the Philosophy
    and Wisdom DNA JSON collections so Reverse DNA (RDNA) pairs can surface the
    substantive synthesis behind a governing stamp, not just the routing indirection.
    """
    index: Dict[str, str] = {}
    for path in (PHILOSOPHY_JSON, WISDOM_JSON):
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                cards = json.load(f)
            for card in cards:
                cid = card.get("id")
                if not cid:
                    continue
                narrative = card.get("synthesis", {}).get("narrative_context", "")
                title = card.get("synthesis", {}).get("title") or card.get("title", "")
                if narrative:
                    index[cid] = narrative
                elif title:
                    index[cid] = title
        except Exception:
            continue
    return index


def build_dna_polymorphic_dataset():
    """
    [FEAT-598 / Story 86.5]
    Builds idiographic stamp recognition and Reverse DNA training pairs from all 5 DNA domains:
    - PHL (Philosophy DNA) -> [PHL-xxx]
    - WIS (Wisdom DNA) -> [WIS-xxx]
    - BKM (Behavioral Protocols) -> [BKM-xxx]
    - FEAT (Feature DNA) -> [FEAT-xxx]
    - RDNA (Reverse DNA) -> Natural Language Queries -> Target DNA Stamps
    """
    print(f"Building Polymorphic DNA Dataset -> {DNA_OUT}")
    dataset = []

    # 1. Ingest Philosophy DNA (PHL)
    if PHILOSOPHY_JSON.exists():
        try:
            with open(PHILOSOPHY_JSON, "r", encoding="utf-8") as f:
                phl_cards = json.load(f)
            for card in phl_cards:
                cid = card.get("id", "PHL-UNK")
                title = card.get("synthesis", {}).get("title") or card.get("title", "")
                narrative = card.get("synthesis", {}).get("narrative_context", "")
                quote = card.get("origin", {}).get("text", "")
                anchors = card.get("synthesis", {}).get("lab_anchors", [])
                
                # Idiographic stamp prompt
                dataset.append({
                    "instruction": f"Explain the architectural philosophy defined in [{cid}] ({title}).",
                    "input": "",
                    "output": f"ID: [{cid}]\nTitle: {title}\nOrigin Quote: \"{quote}\"\n\nSynthesis: {narrative}\nLab Anchors: {', '.join(anchors)}"
                })
                # Concept prompt
                dataset.append({
                    "instruction": f"What is the core principle of '{title}' in the Federated Lab?",
                    "input": "",
                    "output": f"Governed by [{cid}]: {narrative}"
                })
        except Exception as pe:
            print(f"⚠️ Warning reading {PHILOSOPHY_JSON}: {pe}")

    # 2. Ingest Wisdom DNA (WIS)
    if WISDOM_JSON.exists():
        try:
            with open(WISDOM_JSON, "r", encoding="utf-8") as f:
                wis_cards = json.load(f)
            for card in wis_cards:
                cid = card.get("id", "WIS-UNK")
                title = card.get("synthesis", {}).get("title") or card.get("title", "")
                narrative = card.get("synthesis", {}).get("narrative_context", "")
                origin = card.get("origin", {}).get("text", "")
                
                dataset.append({
                    "instruction": f"Recall empirical validation findings from [{cid}] ({title}).",
                    "input": "",
                    "output": f"[{cid}] {title}:\n{narrative}\n\nEmpirical Root: {origin}"
                })
        except Exception as we:
            print(f"⚠️ Warning reading {WISDOM_JSON}: {we}")

# 3. Ingest Reverse DNA (RDNA) Questions
    if RDNA_JSON.exists():
        try:
            with open(RDNA_JSON, "r", encoding="utf-8") as f:
                rdna_entries = json.load(f)
            # [Story 865] Enrich RDNA outputs with the substantive synthesis behind
            # each governing stamp — the model must learn the answer substance, not
            # just the routing indirection (Finding 5 of SPRINT_86 report).
            synthesis_index = _build_dna_synthesis_index()
            for item in rdna_entries:
                qid = item.get("id", "RDNA-UNK")
                target_dna = item.get("target_dna", {})
                target_id = target_dna.get("id", "")
                target_title = target_dna.get("title", "")
                primary_q = item.get("question", "")
                variants = item.get("question_variants", [])
                collection = target_dna.get("collection", "philosophy_dna")
                synthesis = synthesis_index.get(target_id, "")

                for q in ([primary_q] + variants):
                    if q:
                        stamp_line = f"This inquiry is governed by [{target_id}] ({target_title}). Refer to CLaRa-DNA collection '{collection}'."
                        if synthesis:
                            stamp_line += f"\n\nSynthesis: {synthesis[:600]}"
                        dataset.append({
                            "instruction": f"Resolve engineering inquiry to governing DNA: '{q}'",
                            "input": "",
                            "output": stamp_line
                        })
        except Exception as re_err:
            print(f"⚠️ Warning reading {RDNA_JSON}: {re_err}")

    # 4. Ingest Protocols (BKM) from Protocols.md
    if PROTOCOLS_MD.exists():
        try:
            import re
            content = PROTOCOLS_MD.read_text(encoding="utf-8")
            bkm_sections = re.findall(r"(###?\s*\[(BKM-\d+)\].*?)(?=###?\s*\[BKM-\d+\]|\Z)", content, re.DOTALL)
            for sec_text, bkm_id in bkm_sections:
                header_line = sec_text.strip().split("\n")[0]
                title_match = re.search(r"\[(BKM-\d+)\]\s*(.*?)(?:\n|\Z)", header_line)
                name = title_match.group(2).strip() if title_match else bkm_id
                dataset.append({
                    "instruction": f"What is the operational mandate and objective of protocol [{bkm_id}] ({name})?",
                    "input": "",
                    "output": sec_text.strip()[:1000]
                })
        except Exception as bke:
            print(f"⚠️ Warning reading {PROTOCOLS_MD}: {bke}")

    # 5. Ingest Feature DNA (FEAT) from FeatureTracker.md
    # [Story 865] Previously FEATURES_MD was defined and never referenced — 430+
    # FEAT entries produced zero training pairs (Finding 5 of SPRINT_86 report).
    if FEATURES_MD.exists():
        try:
            import re
            content = FEATURES_MD.read_text(encoding="utf-8")
            feat_sections = re.findall(r"(^##+\s*\[(FEAT-\d+)\].*?)(?=^##+\s*\[FEAT-\d+\]|\Z)", content, re.MULTILINE | re.DOTALL)
            for sec_text, feat_id in feat_sections:
                header_line = sec_text.strip().split("\n")[0]
                name = re.sub(r"^##+\s*\[FEAT-\d+\]\s*", "", header_line).strip()
                # Drop trailing tags like [SCAR #5] and leading/embedded [DEFEATURED] markers.
                name = re.sub(r"\s*\[(?:SCAR #?\d+|DEFEATURED)\]\s*$", "", name).strip()
                name = re.sub(r"^\s*\[DEFEATURED\]\s*", "", name).strip()
                if not name:
                    name = feat_id
                fields = {
                    k.strip(): re.sub(r"\s+", " ", v).strip()[:600]
                    for k, v in re.findall(r"\*\*([A-Za-z #0-9]+):\*\*\s*(.*?)(?=\n\*\*|\Z)", sec_text, re.DOTALL)
                }

                # Idiographic feature card prompt
                card_parts = [f"ID: [{feat_id}]", f"Title: {name}"]
                status = fields.get("Status", "")
                if status:
                    card_parts.append(f"Status: {status}")
                for label in ("Logic", "Rationale", "Mechanism", "Reason", "Verification"):
                    value = fields.get(label, "")
                    if value:
                        card_parts.append(f"{label}: {value}")
                dataset.append({
                    "instruction": f"Explain the technical capability defined in [{feat_id}] ({name}).",
                    "input": "",
                    "output": "\n".join(card_parts)
                })
                # Implementation mechanism prompt (stamp + substantive mechanism)
                mechanism = fields.get("Mechanism", "")
                if mechanism:
                    dataset.append({
                        "instruction": f"How is the Feature DNA defined in [{feat_id}] ({name}) implemented in the Federated Lab?",
                        "input": "",
                        "output": f"Governed by [{feat_id}] ({name}): {mechanism}"
                    })
        except Exception as fe:
            print(f"⚠️ Warning reading {FEATURES_MD}: {fe}")

    # Write output
    DNA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DNA_OUT, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")

    print(f"✅ Polymorphic DNA Forge Ready: {len(dataset)} pairs -> {DNA_OUT}")
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
    [FEAT-160] / [Story 86.5]
    Assembles master_forge_curriculum.jsonl with strict curriculum ratios:
      - 30% User Voice & Cadence
      - 25% Engineering Pedigree & BKMs
      - 25% Polymorphic DNA & Idiographic Stamps (PHL, WIS, FEAT, RDNA)
      - 10% Sentinel Vibe & Triage
      - 10% Curated Rank 4 Pearls
    """
    print("\n--- Assembling Multi-Curriculum Master Forge Dataset ---")
    random.seed(seed)
    dest_path = Path(output_path) if output_path else MASTER_CURRICULUM_OUT

    voice_items = _load_jsonl_dataset(VOICE_OUT)
    history_items = _load_jsonl_dataset(HISTORY_OUT)
    dna_items = _load_jsonl_dataset(DNA_OUT)
    sentinel_items = _load_jsonl_dataset(SENTINEL_OUT)
    gems_items = _load_jsonl_dataset(GEMS_OUT)

    print(f"Pool sizes: Voice={len(voice_items)}, History={len(history_items)}, DNA={len(dna_items)}, Sentinel={len(sentinel_items)}, Gems={len(gems_items)}")

    target_voice = int(target_size * CURRICULUM_DISTRIBUTION["voice"])
    target_history = int(target_size * CURRICULUM_DISTRIBUTION["pedigree"])
    target_dna = int(target_size * CURRICULUM_DISTRIBUTION["dna"])
    target_sentinel = int(target_size * CURRICULUM_DISTRIBUTION["sentinel"])
    target_gems = target_size - (target_voice + target_history + target_dna + target_sentinel)

    def sample_or_upsample(pool: list, target_count: int, label: str) -> list:
        if not pool:
            print(f"⚠️ Warning: Pool '{label}' is empty! Skipping.")
            return []
        stream_key = label.lower()
        if len(pool) >= target_count:
            chosen = random.sample(pool, target_count)
        else:
            print(f"ℹ️ Upsampling '{label}' from {len(pool)} to {target_count} items.")
            chosen = [random.choice(pool) for _ in range(target_count)]
        return [{**item, "stream": stream_key} for item in chosen]

    curriculum = []
    curriculum.extend(sample_or_upsample(voice_items, target_voice, "Voice"))
    curriculum.extend(sample_or_upsample(history_items, target_history, "History"))
    curriculum.extend(sample_or_upsample(dna_items, target_dna, "DNA"))
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
    build_dna_polymorphic_dataset()
    build_master_curriculum(target_size=1000)