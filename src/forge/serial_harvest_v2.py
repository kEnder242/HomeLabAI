#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Serial Harvest v2.0
[SPR-13.0] Tricameral-Aware Extraction Pipeline

Sequential harvesting designed to handle multi-message response flows.
Optimized for 4090 Sovereign inference with wall-clock diagnostics.
"""

import asyncio
import json
import logging
import re
import glob
import time
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
        logging.FileHandler("serial_harvest_v2.log"),
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
        
        temp_file = str(PAGER_LOG) + ".tmp"
        data = []
        if PAGER_LOG.exists():
            with open(PAGER_LOG, "r") as f:
                data = json.load(f)
        
        data.append(alert)
        data = data[-100:]
        
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, str(PAGER_LOG))
    except Exception as e:
        logging.error(f"Pager log failed: {e}")

async def harvest_gem(websocket, prompt, summary, file_path, log_file_path):
    """Sends a query and waits specifically for the final Result message."""
    message = {
        "type": "text_input",
        "content": f"[ARCHIVE_EXTRACT]: {prompt}"
    }
    
    start_time = time.time()
    try:
        await websocket.send(json.dumps(message))
    except Exception as e:
        logging.error(f"Failed to send harvest query: {e}")
        return False

    # The Tricameral Listener: Drain messages until we hit a terminal state
    while True:
        try:
            # High timeout to allow for 4090 cold-starts/deep derivations
            resp = await asyncio.wait_for(websocket.recv(), timeout=180)
            data = json.loads(resp)
            source = data.get("brain_source", "Unknown")
            content = data.get("brain", "")

            # Log intermediate airtime turns for forensics
            if "Result" not in source and "Failover" not in source:
                logging.debug(f"  [Airtime] {source}: {content[:50]}...")
                continue

            # We hit a terminal result
            duration = time.time() - start_time
            logging.info(f"  [Capture] Received {source} in {duration:.2f}s")

            if len(content) < 50:
                logging.warning(f"  [Capture] Response too thin ({len(content)} chars). Skipping.")
                return False
            
            # Success: Save to stage 1
            entry = {
                "summary": summary,
                "raw_text": content,
                "source_file": file_path,
                "log_file": log_file_path,
                "duration_sec": duration,
                "captured_at": time.time()
            }
            with open(RAW_STAGE_1_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
            return True

        except asyncio.TimeoutError:
            logging.warning(f"  [Timeout] 4090 exceeded 180s for: {summary[:30]}")
            return False
        except Exception as e:
            logging.error(f"  [Error] During recv: {e}")
            break
    return False

async def main(limit=None):
    logging.info("Starting Serial Harvest v2.0...")
    processed_count = 0
    
    RAW_STAGE_1_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Identify candidates
    json_files = sorted(glob.glob(str(FIELD_NOTES_DATA_DIR / "*.json")))
    all_gems = []
    for f_path in json_files:
        try:
            with open(f_path, "r") as f:
                data = json.load(f)
                # We only harvest Diamond (4) and above
                gems = [item for item in data if item.get("rank", 0) >= 4]
                for g in gems:
                    all_gems.append((g, f_path))
        except Exception:
            continue

    logging.info(f"Inventory: {len(all_gems)} candidates identified.")

    # Resume Logic
    seen_keys = set()
    if RAW_STAGE_1_FILE.exists():
        with open(RAW_STAGE_1_FILE, 'r') as f_check:
            for line in f_check:
                try:
                    entry = json.loads(line)
                    summary_text = entry.get('summary') or entry.get('synopsis') or entry.get('title')
                    source_file = entry.get('source_file')
                    if summary_text and source_file:
                        seen_keys.add(f"{summary_text}|{source_file}")
                except Exception:
                    pass
    
    if seen_keys:
        logging.info(f"Resume: Skipping {len(seen_keys)} already harvested gems.")

    async with websockets.connect(BRAIN_NODE_URI) as websocket:
        await websocket.recv() # Wait for greeting
        log_to_pager(f"Harvest v2 Started: {len(all_gems)} candidates.")

        for gem, file_path in all_gems:
            # 1. Resolve Identity
            summary = gem.get("summary") or gem.get("synopsis") or gem.get("title")
            gem_key = f"{summary}|{file_path}"
            if not summary or gem_key in seen_keys:
                continue

            # 2. Resolve Year/Context
            filename = Path(file_path).name
            year_match = re.search(r'(20\d\d)', filename)
            log_key = gem.get("log_file")
            
            if not log_key:
                if year_match:
                    log_key = year_match.group(1)
                elif gem.get("date"):
                    date_match = re.search(r'(20\d\d)', str(gem["date"]))
                    if date_match:
                        log_key = date_match.group(1)
            
            # specialized catch for Unknown.json / Orphans
            if not log_key:
                log_key = "2024"
                logging.debug(f"ORPHAN: Defaulting {summary[:20]} to {log_key}")

            # 3. Resolve Files via Manifest (Prioritize JSON/Zoom)
            target_files = []
            is_zoom = False
            
            # Check for JSON aggregate first (The "Zoom" method)
            zoom_path = FIELD_NOTES_DATA_DIR / f"{log_key}.json"
            if zoom_path.exists():
                target_files.append(zoom_path)
                is_zoom = True
            
            if not target_files:
                if str(log_key).upper() in EXPERT_OVERRIDES:
                    target_files.append(KNOWLEDGE_BASE_DIR / EXPERT_OVERRIDES[str(log_key).upper()])
                else:
                    try:
                        with open(MANIFEST_FILE, "r") as mf:
                            manifest = json.load(mf)
                        for fname, meta in manifest.items():
                            m_year = str(meta.get("year", ""))
                            m_desc = str(meta.get("description", "")).upper()
                            
                            is_match = False
                            if m_year:
                                if str(log_key) in m_year:
                                    is_match = True
                                elif "-" in m_year:
                                    try:
                                        start, end = map(int, m_year.split("-"))
                                        if start <= int(log_key) <= end:
                                            is_match = True
                                    except ValueError:
                                        pass
                                    except Exception:
                                        pass
                            
                            if not is_match and str(log_key).upper() in m_desc:
                                is_match = True
                                
                            if is_match:
                                if meta.get("type") in ["LOG", "META", "REFERENCE"]:
                                    target_files.append(KNOWLEDGE_BASE_DIR / fname)
                    except Exception:
                        pass
            
            # [FIX] Final recursive glob fallback for orphaned years/keywords
            if not target_files:
                recursive_search = glob.glob(str(KNOWLEDGE_BASE_DIR / "**" / f"*{log_key}*"), recursive=True)
                for f in recursive_search:
                    if f.endswith(".txt") or f.endswith(".md"):
                        target_files.append(Path(f))

            if not target_files:
                logging.info(f"SKIPPED: No files found for {log_key}")
                continue

            # 4. Execute Harvest across candidate files
            success = False
            valid_targets = [f for f in target_files if f.exists()]
            
            logging.info(f"Harvesting [{processed_count+len(seen_keys)+1}/{len(all_gems)}]: {summary[:50]}")
            
            for target_path in valid_targets:
                if is_zoom:
                    prompt = (
                        f"Find the specific chronological entries in the provided JSON context "
                        f"that correspond to this summary: '{summary}'.\n"
                        "Output ONLY the relevant technical blocks, no conversational filler."
                    )
                else:
                    prompt = (
                        f"Find the specific paragraphs in the raw file ({target_path.name}) "
                        f"that correspond to this summary: '{summary}'. Output ONLY the raw "
                        "paragraphs, no conversational filler."
                    )

                if await harvest_gem(websocket, prompt, summary, file_path, str(target_path)):
                    success = True
                    break # Captured! Move to next gem.
            
            if success:
                processed_count += 1
                total = processed_count + len(seen_keys)
                pct = int((total / len(all_gems)) * 100)
                if total % 5 == 0:
                    log_to_pager(f"Harvest Progress: {total}/{len(all_gems)} ({pct}%)")
                
                if limit and processed_count >= limit:
                    logging.info(f"Limit reached ({limit}).")
                    return
            else:
                logging.warning(f"Failed to capture gem across {len(valid_targets)} candidates.")
                # Mark as seen to avoid infinite retries in this session
                seen_keys.add(summary)

            # Keep OLLAMA from unloading if we are between files
            await asyncio.sleep(2.0)

    logging.info(f"Done. Harvested {processed_count} new gems.")

if __name__ == "__main__":
    import sys
    limit_val = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit_val = int(arg.split('=')[1])
    asyncio.run(main(limit=limit_val))
