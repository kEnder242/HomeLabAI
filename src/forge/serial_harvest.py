#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Serial Harvest (Stage 1: Capture v12.1)
[FEAT-202] Decoupled Extraction Pipeline

Strictly sequential harvesting to ensure 100% gem capture.
Leverages FEAT-205 Long-Tail Gate for remote model loading.
"""

import json
import logging
import re
import glob
from pathlib import Path
import websockets

# --- Configuration ---
LOG_LEVEL = logging.INFO
FIELD_NOTES_DATA_DIR = Path.home() / "Dev_Lab/Portfolio_Dev/field_notes/data"
PAGER_LOG = FIELD_NOTES_DATA_DIR / "pager_activity.json"
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

def log_to_pager(message, severity="info"):
    """[FEAT-045] Appends induction status to the status.html interleaved logs."""
    try:
        from datetime import datetime
        import os
        
        alert = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "Induction",
            "severity": severity,
            "message": message
        }
        
        # [BKM-022] Atomic File Swap
        temp_file = str(PAGER_LOG) + ".tmp"
        data = []
        if PAGER_LOG.exists():
            with open(PAGER_LOG, "r") as f:
                data = json.load(f)
        
        data.append(alert)
        # Keep last 100 entries to prevent bloat
        data = data[-100:]
        
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, str(PAGER_LOG))
    except Exception as e:
        logging.error(f"Pager log failed: {e}")

async def harvest_gem(websocket, prompt, summary, file_path, log_file_path):
    """Sends a single extraction query and waits for the result."""
    message = {
        "type": "text_input",
        "content": f"[ARCHIVE_EXTRACT]: {prompt}"
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            send_start_time = asyncio.get_event_loop().time()
            await websocket.send(json.dumps(message))
            send_end_time = asyncio.get_event_loop().time()
            logging.info(f"Prompt sent. Send time: {send_end_time - send_start_time:.2f}s")

            # Wait for completion (Brain Result)
            recv_start_time = asyncio.get_event_loop().time()
            resp = await asyncio.wait_for(websocket.recv(), timeout=60) # Shortened timeout to fail faster
            recv_end_time = asyncio.get_event_loop().time()
            llm_call_duration = recv_end_time - recv_start_time
            logging.info(f"LLM Call duration: {llm_call_duration:.2f}s")

            data = json.loads(resp)

            # Check for Brain Result
            if "Brain" in data.get("brain_source", "") and "Result" in data.get("brain_source", ""):
                result_text = data.get("brain", "")
                if len(result_text) < 50:
                    logging.warning(f"Capture too thin ({len(result_text)} chars). Attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(2) # Small delay before retry
                    continue # Retry

                # Save to raw_stage_1.jsonl
                entry = {
                    "summary": summary,
                    "raw_text": result_text,
                    "source_file": file_path,
                    "log_file": log_file_path,
                    "timestamp": Path(file_path).stat().st_mtime
                }
                with open(RAW_STAGE_1_FILE, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                return True
            else:
                # Handle unexpected response types, treat as failure for retry
                logging.warning(f"Unexpected response format from Brain: {data}. Attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(2)
                continue # Retry

        except asyncio.TimeoutError:
            logging.warning(f"Harvest timeout waiting for response (LLM call took too long). Attempt {attempt + 1}/{max_retries}")
            await asyncio.sleep(2) # Small delay before retry
            continue # Retry
        except Exception as e:
            logging.error(f"Error during recv: {e}")
            # If any other exception occurs, break the retry loop for this gem
            break
    # If all retries fail
    logging.error(f"Failed to harvest gem after {max_retries} attempts.")
    return False

async def main(limit=None):
    logging.info("Starting Serial Harvest (v12.1)...")
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

    # [FEAT-202] Resume Logic: Skip already harvested gems
    seen_summaries = set()
    if RAW_STAGE_1_FILE.exists():
        with open(RAW_STAGE_1_FILE, 'r') as f_check:
            for line in f_check:
                try:
                    entry = json.loads(line)
                    # Track all possible identifiers to prevent re-harvesting
                    for key in ['summary', 'synopsis', 'title']:
                        if entry.get(key):
                            seen_summaries.add(entry[key])
                except Exception:
                    pass
    
    if seen_summaries:
        logging.info(f"Resume: Found {len(seen_summaries)} already in manifest.")

    async with websockets.connect(BRAIN_NODE_URI) as websocket:
        # Wait for greeting
        await websocket.recv()
        
        log_to_pager(f"Harvest Cycle Started: {len(all_gems)} gems identified.")

        # track total progress including resumed
        total_captured = len(seen_summaries)

        for gem, file_path in all_gems:
            loop_start = asyncio.get_event_loop().time()
            # [FIX] Synopsis fallback for missing summary
            summary = gem.get("summary") or gem.get("synopsis") or gem.get("title")
            
            if not summary or summary in seen_summaries:
                continue

            filename = Path(file_path).name
            year_match = re.search(r'(20\d\d)', filename)
            
            # 1. Use log_file key, or filename year, or date field year
            log_key = gem.get("log_file")
            if not log_key:
                if year_match:
                    log_key = year_match.group(1)
                elif gem.get("date"):
                    # Robust date parsing for Unknown.json entries
                    date_val = str(gem["date"])
                    date_match = re.search(r'(20\d\d)', date_val)
                    if date_match:
                        log_key = date_match.group(1)
            
            # Specialized catch for GIT
            if not log_key and summary and "GIT" in summary.upper():
                log_key = "GIT"
            
            # [FIX] specialized catch for Unknown.json / Orphaned gems
            if not log_key:
                log_key = "2024" # Default to 2024 to at least attempt a harvest
                logging.info(f"ORPHAN detected: Defaulting to {log_key} for {summary[:30]}")

            if not summary:
                logging.info(f"SKIPPED: No summary for {file_path}")
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
                                    try:
                                        if start <= int(log_key) <= end:
                                            is_match = True
                                    except ValueError:
                                        pass
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
            success = False
            valid_targets = [f for f in target_files if f.exists()]
            if not valid_targets:
                logging.warning(f"SKIPPED: No physical files found for key '{log_key}'")
                continue

            for log_file_path in valid_targets:
                prompt = (
                    f"Find the specific paragraphs in the raw file ({log_file_path.name}) "
                    f"that correspond to this summary: '{summary}'. Output ONLY the raw "
                    "paragraphs, no conversational filler."
                )

                logging.info(f"Harvesting gem [{total_captured+1}/{len(all_gems)}] from {log_file_path.name}...")
                if await harvest_gem(websocket, prompt, summary, file_path, str(log_file_path)):
                    success = True
                    break # [CRITICAL FIX] Break on first success
            
            if success:
                processed_count += 1
                total_captured += 1
                progress_pct = int((total_captured / len(all_gems)) * 100)
                logging.info(f"Successfully captured gem. Progress: {total_captured}/{len(all_gems)} ({progress_pct}%)")
                
                if total_captured % 5 == 0 or total_captured == len(all_gems):
                    logging.info(f"Harvest Progress: {total_captured}/{len(all_gems)} ({progress_pct}%)")

                if limit and processed_count >= limit:
                    logging.info(f"Limit reached ({limit}). Stopping harvest.")
                    log_to_pager(f"Harvest Stalled: Limit {limit} reached.")
                    return
            else:
                logging.warning(f"Failed to capture gem after exhausting {len(valid_targets)} files: {summary[:50]}")
                # [CRITICAL FIX] Mark as seen to prevent infinite session stall on this specific summary
                seen_summaries.add(summary)
            
            # [FEAT-202] Dynamic Cadence
            MIN_CADENCE = 5.0 
            elapsed = asyncio.get_event_loop().time() - loop_start
            sleep_time = max(0.1, MIN_CADENCE - elapsed)
            await asyncio.sleep(sleep_time)

    log_to_pager(f"Harvest Cycle Finished. Total gems: {processed_count}")
    logging.info(f"Serial Harvest Finished. Total gems captured: {processed_count}")

if __name__ == "__main__":
    import sys
    limit_val = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit_val = int(arg.split('=')[1])
    asyncio.run(main(limit=limit_val))
