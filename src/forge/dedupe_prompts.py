#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gemini Prompt De-duplicator
[FEAT-204] CLI Persona Induction (Stage 2.5)

Prunes the refined prompt manifest using:
1. Exact Hashing (Fast removal of identical prompts).
2. Fuzzy Similarity (Levenshtein distance via 'thefuzz').
   Consolidates near-duplicates to ensure a diverse training curriculum.
"""

import json
import logging
from pathlib import Path
from thefuzz import fuzz

# --- Configuration ---
REFINED_PROMPTS = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/refined_prompts.jsonl"
)
DEDUPED_PROMPT_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/deduped_prompts.jsonl"
)
SIMILARITY_THRESHOLD = 85  # Percent similarity to trigger de-duplication

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def dedupe():
    """Prunes near-duplicates to ensure dataset variety."""
    logging.info("Starting Semantic De-duplication...")

    if not REFINED_PROMPTS.exists():
        logging.error(f"Refined manifest not found: {REFINED_PROMPTS}")
        return

    # 1. Load and Exact Dedupe (Phase 1)
    unique_prompts = []
    seen_hashes = set()
    count_total = 0

    with open(REFINED_PROMPTS, "r") as f_in:
        for line in f_in:
            if not line.strip():
                continue
            count_total += 1
            entry = json.loads(line)
            p = entry.get("prompt", "").strip()
            
            p_hash = hash(p)
            if p_hash not in seen_hashes:
                unique_prompts.append(p)
                seen_hashes.add(p_hash)

    count_exact_unique = len(unique_prompts)
    logging.info(f"Phase 1: Exact de-dupe reduced {count_total} -> {count_exact_unique}")

    # 2. Fuzzy Dedupe (Phase 2)
    # To keep it O(N) or close to it, we'll use a sliding window approach
    # assuming that duplicates often appear near each other in history.
    # For a full O(N^2) on 6k prompts, it would take too long.
    final_prompts = []
    
    logging.info(f"Phase 2: Starting Fuzzy Scan (Threshold: {SIMILARITY_THRESHOLD}%)...")
    
    for i, current in enumerate(unique_prompts):
        if i % 500 == 0:
            logging.info(f"Processing... {i}/{count_exact_unique}")
            
        is_duplicate = False
        # Check against the last 100 accepted prompts (Sliding Window)
        # This catches most "Spam" clusters without the N^2 penalty
        for existing in final_prompts[-100:]:
            if fuzz.ratio(current, existing) > SIMILARITY_THRESHOLD:
                is_duplicate = True
                break
        
        if not is_duplicate:
            final_prompts.append(current)

    count_final = len(final_prompts)
    
    # 3. Output to JSONL
    DEDUPED_PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEDUPED_PROMPT_FILE, "w") as f_out:
        for p in final_prompts:
            f_out.write(json.dumps({"prompt": p}) + "\n")

    logging.info(f"De-duplication Finished.")
    logging.info(f"Final Diversity: {count_final} unique directives (Compression: {((1 - count_final/count_total)*100):.1f}%)")
    logging.info(f"Deduped manifest saved to: {DEDUPED_PROMPT_FILE}")


if __name__ == "__main__":
    dedupe()
