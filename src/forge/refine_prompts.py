#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gemini Prompt Refiner
[FEAT-204] CLI Persona Induction (Stage 2)

Filters the consolidated prompt manifest to remove:
1. Short fragments (< 10 chars).
2. Raw debug logs (SSH, Windows version strings).
3. Repetitive path fragments.
"""

import json
import logging
import re
from pathlib import Path

# --- Configuration ---
PROMPT_MANIFEST = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/gemini_prompts_manifest.jsonl"
)
REFINED_PROMPT_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/refined_prompts.jsonl"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def is_debug_noise(text):
    """Detects raw terminal/debug output."""
    noise_patterns = [
        r"^debug\d:",  # SSH Debug
        r"^OpenSSH_",  # SSH Headers
        r"^C:\\Users\\",  # Windows paths
        r"^Windows version:",
        r"^WSL version:",
        r"^Kernel version:",
        r"^Direct3D version:",
        r"^DXCore version:",
        r"^jason@kEnder:",  # Shell prompts
        r"^OpenSSL",
    ]
    for pattern in noise_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def refine():
    """Filters the manifest into a high-fidelity voice dataset."""
    logging.info("Starting Prompt Refinement...")

    if not PROMPT_MANIFEST.exists():
        logging.error(f"Manifest not found: {PROMPT_MANIFEST}")
        return

    count_total = 0
    count_refined = 0

    with open(PROMPT_MANIFEST, "r") as f_in, open(REFINED_PROMPT_FILE, "w") as f_out:
        for line in f_in:
            if not line.strip():
                continue

            count_total += 1
            try:
                entry = json.loads(line)
                prompt = entry.get("prompt", "").strip()

                # 1. Length Gate
                if len(prompt) < 15:
                    continue

                # 2. Debug Noise Filter
                if is_debug_noise(prompt):
                    continue

                # 3. Structural Cleaning
                # Remove common artifacts like '{"prompt": ...}' if double wrapped
                if prompt.startswith('{"prompt":'):
                    try:
                        inner = json.loads(prompt)
                        prompt = inner.get("prompt", prompt)
                    except Exception:
                        pass

                # Save refined prompt
                f_out.write(json.dumps({"prompt": prompt}) + "\n")
                count_refined += 1

            except Exception as e:
                logging.error(f"Error processing line: {e}")

    logging.info(
        f"Refinement Finished. Total: {count_total}, High-Fidelity: {count_refined}"
    )
    logging.info(f"Refined manifest saved to: {REFINED_PROMPT_FILE}")


if __name__ == "__main__":
    refine()
