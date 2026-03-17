#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Deep-Connect Epoch v2 (Stage 2: Surgical Refinement)
[FEAT-202] Decoupled Extraction Pipeline

This script performs the "Refinement" phase:
1. Reading `expertise/raw_stage_1.jsonl`.
2. Applying the Nuclear JSON Clean logic to extract raw paragraphs.
3. Appending successfully parsed pairs to `bkm_master_manifest.jsonl`.
"""

import json
import logging
import re
from pathlib import Path

# --- Configuration ---
LOG_LEVEL = logging.INFO
RAW_STAGE_1_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/raw_stage_1.jsonl"
)
BKM_MANIFEST_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/bkm_master_manifest.jsonl"
)

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("deep_connect_refinement.log"),
    ],
)


def bridge_signal_clean(text):
    """Refined JSON extraction logic from the experiment."""
    if "{" not in text:
        return text.strip()

    # 1. Strip markdown blocks
    clean = re.sub(r"```json\s*|\s*```", "", text)

    # 2. Find innermost { } block
    match = re.search(r"(\{.*\})", clean, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Salvage truncated JSON
        if "{" in clean:
            json_str = clean[clean.find("{") :] + '\n  "error": "truncated"\n}'
        else:
            return None

    # 3. Structural Sanitization
    json_str = json_str.replace("{{", "{").replace("}}", "}")
    json_str = json_str.replace("'", '"')
    json_str = json_str.replace("True", "true").replace("False", "false")

    # 4. Domain Multi-Pick Correction
    json_str = re.sub(
        r'("domain":\s*"[^"]+")((?:,\s*"[^"]+")+)(?=\s*,|\s*\})', r"\1", json_str
    )
    # Clean up trailing commas
    json_str = re.sub(r",\s*\}", r"\n}", json_str)

    return json_str


def main():
    """Main function to refine raw blocks into high-density BKM pairs."""
    logging.info("Starting Deep-Connect Stage 2 (Refinement)...")
    
    if not RAW_STAGE_1_FILE.exists():
        logging.error(f"Stage 1 buffer not found: {RAW_STAGE_1_FILE}")
        return

    BKM_MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BKM_MANIFEST_FILE.exists():
        BKM_MANIFEST_FILE.touch()

    count_success = 0
    count_fail = 0

    with open(RAW_STAGE_1_FILE, "r") as raw_f:
        for line in raw_f:
            if not line.strip():
                continue
            
            try:
                entry = json.loads(line)
                # [FIX] Handle both legacy and v2 harvest field names
                raw_text = entry.get("raw_text") or entry.get("raw_llm_output", "")
                summary = entry.get("summary", "")
                
                # Apply Bridge Signal Clean
                clean_json = bridge_signal_clean(raw_text)
                
                # [FIX] If clean_json fails but raw_text exists, 
                # salvage the raw technical block for extraction integrity.
                if not clean_json and len(raw_text) > 100:
                    clean_json = json.dumps({
                        "bkm_content": raw_text,
                        "logic": "Direct extraction salvage",
                        "status": "RAW"
                    })
                
                if clean_json:
                    try:
                        context = clean_json
                        if clean_json.startswith("{"):
                            data = json.loads(clean_json)
                            context = data.get("context") or data.get("situation") or clean_json
                        
                        bkm_pair = {
                            "summary": summary,
                            "context": context,
                            "source_file": entry.get("source_file"),
                            "log_file": entry.get("log_file"),
                            "refined_at": entry.get("timestamp")
                        }
                        
                        with open(BKM_MANIFEST_FILE, "a") as out_f:
                            out_f.write(json.dumps(bkm_pair) + "\n")
                        
                        count_success += 1
                    except json.JSONDecodeError:
                        # If it's not JSON, it might just be the raw paragraphs as requested
                        bkm_pair = {
                            "summary": summary,
                            "context": raw_text.strip(),
                            "source_file": entry.get("source_file"),
                            "log_file": entry.get("log_file"),
                            "refined_at": entry.get("timestamp")
                        }
                        with open(BKM_MANIFEST_FILE, "a") as out_f:
                            out_f.write(json.dumps(bkm_pair) + "\n")
                        count_success += 1
                else:
                    count_fail += 1
            except Exception as e:
                logging.error(f"Error processing line: {e}")
                count_fail += 1

    logging.info(f"Refinement Finished. Success: {count_success}, Fail: {count_fail}")


if __name__ == "__main__":
    main()
