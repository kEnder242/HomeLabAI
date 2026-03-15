#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gemini Prompt Extractor
[FEAT-204] CLI Persona Induction

Aggregates historical prompt data from:
1. all_gemini_history.json (Pre-Jan 13)
2. ~/.gemini/tmp/**/chats/*.json (Post-Jan 13)

Outputs a consolidated JSONL for LoRA training.
"""

import json
import glob
from pathlib import Path

# --- Configuration ---
HISTORY_JSON = Path.home() / "Dev_Lab/all_gemini_history.json"
GEMINI_TMP = Path.home() / ".gemini/tmp"
OUTPUT_FILE = Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/gemini_prompts_manifest.jsonl"

def extract_from_history():
    """Extracts prompts from the pre-Jan 13 archive using jq."""
    import subprocess
    prompts = []
    if not HISTORY_JSON.exists():
        return prompts
    
    print(f"Extracting from {HISTORY_JSON} using jq...")
    try:
        # Command to pull user content from multiple objects
        cmd = "jq -r '.messages[] | select(.type == \"user\") | .content' " + str(HISTORY_JSON)
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            prompts = [p.strip() for p in result.stdout.split('\n') if p.strip()]
    except Exception as e:
        print(f"Error using jq: {e}")
        
    return prompts

def extract_from_tmp():
    """Extracts prompts from the local session logs."""
    prompts = []
    print(f"Scanning {GEMINI_TMP} for sessions...")
    
    chat_files = glob.glob(str(GEMINI_TMP / "**/chats/*.json"), recursive=True)
    print(f"Found {len(chat_files)} session files.")
    
    for chat_file in chat_files:
        try:
            with open(chat_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "messages" in data:
                    for msg in data["messages"]:
                        if msg.get("type") == "user" and msg.get("content"):
                            content = msg["content"]
                            if isinstance(content, list):
                                content = " ".join([str(c) for c in content])
                            prompts.append(content)
        except Exception as e:
            print(f"Error reading {chat_file}: {e}")
            
    return prompts

def main():
    all_prompts = []
    
    # 1. Old History
    old_prompts = extract_from_history()
    all_prompts.extend(old_prompts)
    print(f"Extracted {len(old_prompts)} from history.")
    
    # 2. Local Sessions
    new_prompts = extract_from_tmp()
    all_prompts.extend(new_prompts)
    
    print(f"Total prompts extracted: {len(all_prompts)}")
    
    # 3. Output to JSONL
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        for p in all_prompts:
            # Format: simple prompt for now, or instruction pair if we have gemini response
            entry = {"prompt": p}
            f.write(json.dumps(entry) + "\n")
            
    print(f"Consolidated manifest written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
