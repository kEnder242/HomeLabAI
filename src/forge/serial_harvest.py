#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Serial Harvest (Stage 1: Capture v12)
[FEAT-202] Decoupled Extraction Pipeline

Strictly sequential harvesting to ensure 100% gem capture.
Leverages FEAT-205 Long-Tail Gate for Windows GPU residency.
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
MANIFEST_FILE = Path.home() / "Dev_Lab/Portfolio_Dev/field_notes/data/file_manifest.json"
KNOWLEDGE_BASE_DIR = Path.home() / "Dev_Lab/knowledge_base"

# Specialized Expert Overrides
EXPERT_OVERRIDES = {
    "GIT": "notes_GIT.txt",
    "INSIGHTS": "11066402 Insights 2019-2024.txt",
    "ERA": "project_8149f759.md"
}

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("serial_harvest.log"),
    ],
)

async def harvest_gem(websocket, prompt, summary, file_path, log_file_path):
    """Sends a single extraction query and waits for the result."""
    message = {
        "type": "text_input",
        "content": f"[ARCHIVE_EXTRACT]: {prompt}"
    }
    await websocket.send(json.dumps(message))
    
    # We wait up to 120s for the remote 4090 to respond (including load time)
    start_time = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start_time) < 120:
        try:
            resp = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(resp)
            source = data.get("brain_source", "")
            text = data.get("brain", "")
            
            # Look for Result from either hemisphere
            if ("Lab" in source or "Brain" in source) and "Result" in source:
                entry = {
                    "summary": summary,
                    "raw_llm_output": text,
                    "source_file": str(file_path),
                    "log_file": log_file_path,
                    "timestamp": Path(file_path).stat().st_mtime
                }
                with open(RAW_STAGE_1_FILE, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                return True
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logging.error(f"Error during recv: {e}")
            break
    return False

async def main():
    logging.info("Starting Serial Harvest (v12)...")
    processed_count = 0
    
    RAW_STAGE_1_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    json_files = sorted(glob.glob(str(FIELD_NOTES_DATA_DIR / "*.json")))
    all_gems = []
    
    for f_path in json_files:
        try:
            with open(f_path, "r") as f:
                data = json.load(f)
                gems = [item for item in data if item.get("rank", 0) >= 4]
                for g in gems:
                    all_gems.append((g, f_path))
        except Exception:
            continue

    logging.info(f"Found {len(all_gems)} Rank 4+ gems to harvest.")

    async with websockets.connect(BRAIN_NODE_URI) as websocket:
        # Wait for greeting
        await websocket.recv()
        
        for gem, file_path in all_gems:
            loop_start = asyncio.get_event_loop().time()
            summary = gem.get("summary")
            filename = Path(file_path).name
            year_match = re.search(r'(20\d\d)', filename)
            
            # 1. Use log_file key, or filename year, or date field year
            log_key = gem.get("log_file")
            if not log_key:
                if year_match:
                    log_key = year_match.group(1)
                elif gem.get("date"):
                    date_match = re.search(r'(20\d\d)', gem["date"])
                    if date_match:
                        log_key = date_match.group(1)
            
            # Specialized catch for GIT
            if not log_key and summary and "GIT" in summary.upper():
                log_key = "GIT"
            
            if not summary or not log_key:
                safe_summary = summary[:30] if summary else "[MISSING_SUMMARY]"
                logging.info(f"SKIPPED: No log_key for {safe_summary} in {file_path}")
                continue

            # 2. Resolve Paths via Manifest (Manifest Authority)
            target_files = []
            if log_key in EXPERT_OVERRIDES:
                target_files.append(KNOWLEDGE_BASE_DIR / EXPERT_OVERRIDES[log_key])
            else:
                try:
                    with open(MANIFEST_FILE, "r") as mf:
                        manifest = json.load(mf)
                    for fname, meta in manifest.items():
                        m_year = str(meta.get("year", ""))
                        is_match = False
                        if m_year:
                            if "-" in m_year:
                                try:
                                    start, end = map(int, m_year.split("-"))
                                    if start <= int(log_key) <= end:
                                        is_match = True
                                except Exception:
                                    pass
                            if not is_match and (str(log_key) in m_year or m_year in str(log_key)):
                                is_match = True
                        
                        if is_match:
                            if meta.get("type") in ["LOG", "META"]:
                                target_files.append(KNOWLEDGE_BASE_DIR / fname)
                except Exception as e:
                    logging.error(f"Manifest Load Failed: {e}")

            if not target_files:
                logging.info(f"SKIPPED: No manifest match for key '{log_key}' ({summary[:30]})")
                continue

            # --- THE HARVEST ---
            for log_file_path in target_files:
                if not log_file_path.exists():
                    continue

                prompt = (
                    f"Find the specific paragraphs in the raw file ({log_file_path.name}) "
                    f"that correspond to this summary: '{summary}'. Output ONLY the raw "
                    "paragraphs, no conversational filler."
                )

                logging.info(f"Harvesting gem [{processed_count+1}/{len(all_gems)}] from {log_file_path.name}...")
                success = await harvest_gem(websocket, prompt, summary, file_path, str(log_file_path))
            
            if success:
                processed_count += 1
                logging.info(f"Successfully captured gem. Progress: {processed_count}/{len(all_gems)}")
            else:
                logging.warning(f"Failed to capture gem: {summary[:50]}")
            
            # [FEAT-202] Dynamic Cadence: Ensure at least a 2s pulse to keep GPU resident, but no extra delay if logic was slow.
            MIN_CADENCE = 5.0 
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0.1, MIN_CADENCE - elapsed)
            await asyncio.sleep(sleep_time)

    logging.info(f"Serial Harvest Finished. Total gems captured: {processed_count}")

if __name__ == "__main__":
    asyncio.run(main())
