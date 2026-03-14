#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Deep-Connect Epoch v2

This script performs the "Deep-Connect Epoch" by:
1. Scanning all `20*.json` files in `Portfolio_Dev/field_notes/data`.
2. Filtering for items with `rank >= 4`.
3. For each "Gem," it calls the Brain Node's `deep_think` tool via an MCP client
   session on ws://localhost:8765.
4. The prompt to the Brain is: "Find the specific paragraphs in the raw log file
   ({log_file_path}) that correspond to this summary: '{summary}'. Output ONLY the
   raw paragraphs, no conversational filler."
5. It extracts the context from the Brain's response.
6. It then formats this into a high-density BKM pair and appends it to
   `HomeLabAI/src/forge/expertise/bkm_master_manifest.jsonl`.
"""

import asyncio
import json
import logging
import os
import glob
from pathlib import Path
import websockets

# --- Configuration ---
LOG_LEVEL = logging.INFO
FIELD_NOTES_DATA_DIR = Path.home() / "Dev_Lab/Portfolio_Dev/field_notes/data"
BKM_MANIFEST_FILE = (
    Path.home() / "Dev_Lab/HomeLabAI/src/forge/expertise/bkm_master_manifest.jsonl"
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
        logging.FileHandler("deep_connect_epoch_v2.log"),
    ],
)


async def call_lab_node(prompt):
    """Calls the Lab Node via the Hub to perform archive extraction."""
    try:
        async with websockets.connect(BRAIN_NODE_URI) as websocket:
            # 1. Wait for Hub Greeting
            greeting = await websocket.recv()
            logging.debug(f"Hub Greeting: {greeting}")

            # 2. Send Extraction Query (Directed to Lab Node)
            message = {
                "type": "text_input",
                "content": f"[ARCHIVE_EXTRACT]: {prompt}"
            }
            await websocket.send(json.dumps(message))
            
            # 3. Collect Parallel Responses
            for _ in range(5):
                try:
                    resp = await asyncio.wait_for(websocket.recv(), timeout=45)
                    data = json.loads(resp)
                    source = data.get("brain_source", "")
                    text = data.get("brain", "")
                    
                    if "Lab" in source and "Result" in source:
                        return text
                except asyncio.TimeoutError:
                    break
            return None
    except Exception as e:
        logging.error(f"Error calling Brain Node: {e}")
        return None


async def main(limit=None):
    """Main function to perform the Deep-Connect Epoch."""
    logging.info("Starting Deep-Connect Epoch v2...")
    processed_count = 0
    BKM_MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not BKM_MANIFEST_FILE.exists():
        BKM_MANIFEST_FILE.touch()

    # 1. Scan all `20*.json` files
    json_files = glob.glob(str(FIELD_NOTES_DATA_DIR / "20*.json"))
    logging.info(f"Found {len(json_files)} field notes files to process.")

    for file_path in json_files:
        logging.info(f"Processing file: {file_path}")
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logging.warning(f"Could not decode JSON from {file_path}. Skipping.")
            continue

        # 2. Filter for items with rank >= 4
        gems = [item for item in data if item.get("rank", 0) >= 4]
        if not gems:
            logging.info(f"No gems with rank >= 4 found in {file_path}.")
            continue

        import re
        for gem in gems:
            summary = gem.get("summary")
            
            # Robust Year Extraction
            filename = Path(file_path).name
            match = re.search(r'(20\d\d)', filename)
            derived_year = match.group(1) if match else None
            
            log_key = gem.get("log_file") or derived_year
            
            if not summary or not log_key:
                logging.warning(f"Gem missing summary or valid log_key in {file_path}. Skipping.")
                continue
            
            log_file_path = LOG_MAP.get(str(log_key))
            if not log_file_path:
                logging.warning(f"Could not find log file path for key: {log_key}. Skipping.")
                continue

            # 4. Create the prompt
            prompt = (
                f"Find the specific paragraphs in the raw log file ({log_file_path}) "
                f"that correspond to this summary: '{summary}'. Output ONLY the raw "
                "paragraphs, no conversational filler."
            )

            # 3. Call the Lab Node
            context = await call_lab_node(prompt)

            if context:
                processed_count += 1
                # 6. Format and append BKM
                bkm_pair = {
                    "summary": summary,
                    "context": context,
                    "source_file": file_path,
                    "log_file": log_file_path,
                }
                with open(BKM_MANIFEST_FILE, "a") as f:
                    f.write(json.dumps(bkm_pair) + "\\n")
                logging.info(f"Appended BKM for summary: {summary}")
                if limit and processed_count >= limit:
                    logging.info(f"Limit reached ({limit}). Stopping epoch.")
                    return

    logging.info("Deep-Connect Epoch v2 finished.")


if __name__ == "__main__":
    import sys
    limit_val = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit_val = int(arg.split('=')[1])
    asyncio.run(main(limit=limit_val))
