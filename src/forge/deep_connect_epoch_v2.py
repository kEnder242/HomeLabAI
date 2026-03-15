#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Deep-Connect Epoch v2 (Stage 1: Raw Capture)
[FEAT-202] Decoupled Extraction Pipeline

This script performs the "Capture" phase:
1. Scanning all `20*.json` files in `Portfolio_Dev/field_notes/data`.
2. Filtering for items with `rank >= 4`.
3. For each "Gem," it calls the Lab Node to extract raw context.
4. It saves the RAW LLM response to `expertise/raw_stage_1.jsonl`.
   NO PARSING happens here to prevent VRAM thrash/wait cycles.
"""

import asyncio
import json
import logging
import glob
import re
from pathlib import Path
import websockets

# --- Configuration ---
LOG_LEVEL = logging.INFO
FIELD_NOTES_DATA_DIR = Path.home() / "Dev_Lab/Portfolio_Dev/field_notes/data"
RAW_STAGE_1_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/raw_stage_1.jsonl"
)
BRAIN_NODE_URI = "ws://localhost:8765"

# LOG_MAP for resolving log file paths
LOG_MAP = {
    "2005": "/home/jallred/Dev_Lab/knowledge_base/notes_2005.txt",
    "2006": "/home/jallred/Dev_Lab/knowledge_base/notes_2006_EPSD.txt",
    "2007": "/home/jallred/Dev_Lab/knowledge_base/notes_2006_EPSD.txt",
    "2008": "/home/jallred/Dev_Lab/knowledge_base/Performance_Review_2008-2018.txt",
    "2009": "/home/jallred/Dev_Lab/knowledge_base/Performance_Review_2008-2018.txt",
    "2010": "/home/jallred/Dev_Lab/knowledge_base/Performance_Review_2008-2018.txt",
    "2011": "/home/jallred/Dev_Lab/knowledge_base/notes_2015_DSD.txt",
    "2012": "/home/jallred/Dev_Lab/knowledge_base/notes_2015_DSD.txt",
    "2013": "/home/jallred/Dev_Lab/knowledge_base/notes_2015_DSD.txt",
    "2014": "/home/jallred/Dev_Lab/knowledge_base/notes_2015_DSD.txt",
    "2015": "/home/jallred/Dev_Lab/knowledge_base/notes_2015_DSD.txt",
    "2016": "/home/jallred/Dev_Lab/knowledge_base/notes_2016_MVE.txt",
    "2017": "/home/jallred/Dev_Lab/knowledge_base/notes_2018_PAE.txt",
    "2018": "/home/jallred/Dev_Lab/knowledge_base/notes_2018_PAE.txt",
    "2019": "/home/jallred/Dev_Lab/knowledge_base/notes_2018_PAE.txt",
    "2020": "/home/jallred/Dev_Lab/knowledge_base/notes_2024_PIAV.txt",
    "2021": "/home/jallred/Dev_Lab/knowledge_base/notes_2024_PIAV.txt",
    "2022": "/home/jallred/Dev_Lab/knowledge_base/notes_2024_PIAV.txt",
    "2023": "/home/jallred/Dev_Lab/knowledge_base/notes_2024_PIAV.txt",
    "2024": "/home/jallred/Dev_Lab/knowledge_base/notes_2024_PIAV.txt",
}


# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("deep_connect_capture.log"),
    ],
)


async def call_lab_node_raw(prompt):
    """Calls the Lab Node and returns the RAW response string."""
    try:
        async with websockets.connect(BRAIN_NODE_URI) as websocket:
            # 1. Wait for Hub Greeting
            await websocket.recv()

            # 2. Send Extraction Query (Directed to Lab Node)
            message = {
                "type": "text_input",
                "content": f"[ARCHIVE_EXTRACT]: {prompt}"
            }
            await websocket.send(json.dumps(message))
            
            # 3. Collect Response
            for _ in range(10): # Increased loop to catch later Brain results
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=60)
                    data = json.loads(resp)
                    source = data.get("brain_source", "")
                    text = data.get("brain", "")
                    
                    # Accept result from either Hemisphere (Brain or Lab)
                    if ("Lab" in source or "Brain" in source) and "Result" in source:
                        return text
                except asyncio.TimeoutError:
                    break
            return None
    except Exception as e:
        logging.error(f"Error calling Brain Node: {e}")
        return None


async def main(limit=None):
    """Main function to perform Stage 1: Raw Capture."""
    logging.info("Starting Deep-Connect Stage 1 (Capture)...")
    processed_count = 0
    RAW_STAGE_1_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure buffer exists
    if not RAW_STAGE_1_FILE.exists():
        RAW_STAGE_1_FILE.touch()

    json_files = glob.glob(str(FIELD_NOTES_DATA_DIR / "20*.json"))
    logging.info(f"Found {len(json_files)} field notes files.")

    for file_path in json_files:
        logging.info(f"Scanning: {file_path}")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception:
            continue

        gems = [item for item in data if item.get("rank", 0) >= 4]
        if not gems:
            continue

        for gem in gems:
            summary = gem.get("summary")
            
            # Robust Year Extraction
            filename = Path(file_path).name
            year_match = re.search(r'(20\d\d)', filename)
            log_key = gem.get("log_file") or (year_match.group(1) if year_match else None)
            
            if not summary or not log_key:
                continue
            
            log_file_path = LOG_MAP.get(str(log_key))
            if not log_file_path:
                continue

            prompt = (
                f"Find the specific paragraphs in the raw log file ({log_file_path}) "
                f"that correspond to this summary: '{summary}'. Output ONLY the raw "
                "paragraphs, no conversational filler."
            )

            # --- THE CAPTURE ---
            logging.info(f"Querying Lab Node for: {summary[:50]}...")
            raw_response = await call_lab_node_raw(prompt)
            await asyncio.sleep(15) # Wait for VRAM/Hub to settle

            if raw_response:
                processed_count += 1
                entry = {
                    "summary": summary,
                    "raw_llm_output": raw_response,
                    "source_file": file_path,
                    "log_file": log_file_path,
                    "timestamp": Path(file_path).stat().st_mtime
                }
                with open(RAW_STAGE_1_FILE, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                
                logging.info(f"Captured [{processed_count}] raw blocks.")
                
                if limit and processed_count >= limit:
                    logging.info(f"Limit reached ({limit}). Stopping Stage 1.")
                    return

    logging.info("Deep-Connect Stage 1 Finished.")


if __name__ == "__main__":
    import sys
    limit_val = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit_val = int(arg.split('=')[1])
    asyncio.run(main(limit=limit_val))
