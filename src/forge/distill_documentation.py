#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Documentation Distiller
[FEAT-T21.1] Generating synthetic Q&A pairs from markdown documentation/BKMs
using the active vLLM base engine.
"""

import sys
import json
import re
import urllib.request
from pathlib import Path

# --- Configuration ---
LAB_DIR = Path("/home/jallred/Dev_Lab/HomeLabAI")
OUTPUT_FILE = LAB_DIR / "src/forge/expertise/bkm_master_manifest.jsonl"
VLLM_URL = "http://localhost:8088/v1/chat/completions"

def query_vllm(prompt: str) -> str:
    """Queries the running vLLM server on port 8088."""
    payload = {
        "model": "unified-base",
        "messages": [
            {"role": "system", "content": "You are a senior system validation engineer preparing synthetic Q&A training pairs. You output ONLY valid JSON lists."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1024
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        VLLM_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res = response.read().decode("utf-8")
            res_json = json.loads(res)
            return res_json["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error querying vLLM: {e}")
        return ""

def clean_json_output(text: str) -> list:
    """Extracts a valid JSON list from LLM output, handling markdown blocks."""
    text_clean = text.strip()
    if text_clean.startswith("```json"):
        text_clean = text_clean[7:]
    if text_clean.startswith("```"):
        text_clean = text_clean[3:]
    if text_clean.endswith("```"):
        text_clean = text_clean[:-3]
    text_clean = text_clean.strip()
    
    try:
        # Search for first [ and last ]
        start = text_clean.find("[")
        end = text_clean.rfind("]")
        if start != -1 and end != -1:
            json_str = text_clean[start:end+1]
            return json.loads(json_str)
        return json.loads(text_clean)
    except Exception as e:
        print(f"Failed to parse JSON content: {e}. Raw: {repr(text)}")
        return []

def distill_file(filepath: Path):
    """Reads a markdown file, splits it by main headers, and generates Q&A pairs."""
    print(f"Distilling file: {filepath}")
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
        
    with open(filepath, "r") as f:
        content = f.read()
        
    # Split content by markdown headers (## or #)
    sections = re.split(r'\n(?=#+ )', content)
    
    pairs_extracted = 0
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, "a") as f_out:
        for sec in sections:
            sec_clean = sec.strip()
            if len(sec_clean) < 150: # Skip small headers or metadata blocks
                continue
                
            prompt = (
                "Analyze this technical documentation section:\n"
                "---\n"
                f"{sec_clean}\n"
                "---\n\n"
                "Generate exactly 1 to 2 detailed Question/Response training pairs based strictly on the text.\n"
                "Each Question (instruction) must ask about specific BKMs, rules, or architectural details.\n"
                "Each Response (output) must state the facts clearly, clinically, and in detail without summary fluff.\n"
                "Format the output strictly as a JSON list of objects:\n"
                "[\n"
                "  {\"instruction\": \"The technical question?\", \"output\": \"The detailed answer.\"}\n"
                "]\n"
                "Return ONLY the raw JSON list. Do not write markdown tags or conversational text."
            )
            
            print(f"Generating QA for section: {sec_clean[:60]}...")
            raw_response = query_vllm(prompt)
            if not raw_response:
                continue
                
            qa_list = clean_json_output(raw_response)
            for qa in qa_list:
                if "instruction" in qa and "output" in qa:
                    # Write format matching history manifest expectations
                    entry = {
                        "summary": qa["instruction"],
                        "raw_text": qa["output"],
                        "context": qa["output"]
                    }
                    f_out.write(json.dumps(entry) + "\n")
                    pairs_extracted += 1
                    
    print(f"Completed distillation for {filepath.name}. Appended {pairs_extracted} pairs to manifest.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python distill_documentation.py <path_to_markdown>")
        sys.exit(1)
        
    target_path = Path(sys.argv[1])
    distill_file(target_path)
