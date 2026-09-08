#!/usr/bin/env python3
"""
[FEAT-557] Sprint DNA Vector Synchronizer & Archiving Distillation Queue
Ingests all archived sprint plans from Portfolio_Dev/docs/sprints/archive/
into ChromaDB collection 'sprint_dna' on port 8001 using a hybrid chunking model:
  - Level 1: Story Cards (Story ID, prompts, touched files, lessons learned)
  - Level 2: Sprint Overview (Themes, executive summary, retrospective)
Applies a discrete 3-tier recency decay model:
  - Active Sprint: 1.0
  - Past 5 Sprints: 0.85
  - Older Archived Sprints: 0.30
"""

import os
import re
import sys
import glob
import json
import time
import logging
import chromadb
from chromadb.utils import embedding_functions

ARCHIVE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/docs/sprints/archive")
ACTIVE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/docs/sprints/active")
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_SPRINT = "sprint_dna"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_chroma_client():
    try:
        logging.info("Connecting to ChromaDB HttpClient on port 8001...")
        client = chromadb.HttpClient(host="127.0.0.1", port=8001)
        client.heartbeat()
        return client
    except Exception as e:
        logging.warning(f"HttpClient connection failed: {e}. Falling back to PersistentClient.")
        return chromadb.PersistentClient(path=DB_PATH)


def extract_sprint_number(filename: str) -> float:
    match = re.search(r"SPR_(\d+)(?:_(\d+))?", filename)
    if match:
        major = float(match.group(1))
        minor = float(match.group(2)) if match.group(2) else 0.0
        return major + (minor / 10.0)
    return 0.0


def calculate_recency_weight(sprint_num: float, max_sprint: float) -> float:
    delta = max_sprint - sprint_num
    if delta <= 0.5:
        return 1.00  # Active sprint tier
    elif delta <= 5.5:
        return 0.85  # Past 5 sprints tier
    else:
        return 0.30  # Older archived sprints tier


def parse_sprint_file(filepath: str, max_sprint: float):
    filename = os.path.basename(filepath)
    sprint_num = extract_sprint_number(filename)
    recency_weight = calculate_recency_weight(sprint_num, max_sprint)
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    chunks = []

    # Level 2: Sprint Overview Chunk
    overview_match = re.search(r"#+\s*(.*?)\n(.*?)(?=\n#+\s*⏱️|\n#+\s*🧬|\n#+\s*Story|\Z)", content, re.DOTALL)
    if overview_match:
        title = overview_match.group(1).strip()
        body = overview_match.group(2).strip()
        doc_overview = f"SPRINT OVERVIEW: SPR_{sprint_num}\nTitle: {title}\nFile: {filename}\nRecency Weight: {recency_weight}\n\n{body[:1500]}"
        chunks.append({
            "id": f"SPR_{sprint_num}_OVERVIEW",
            "document": doc_overview,
            "metadata": {
                "sprint_id": f"SPR_{sprint_num}",
                "level": "SPRINT_OVERVIEW",
                "recency_weight": recency_weight,
                "source": filename,
                "type": "SPRINT_DNA"
            }
        })

    # Level 1: Story Cards
    story_pattern = re.compile(r"(#{2,4}\s*(?:⏱️|🧬)?\s*(?:Story\s*([\d\.]+[A-Za-z]?)|([A-Z0-9_\-\.]+))\s*[:\-\s]*(.*?))\n(.*?)(?=\n#{2,4}\s*(?:⏱️|🧬)?\s*Story|\n#{2,4}\s*📊|\Z)", re.DOTALL | re.IGNORECASE)
    
    for idx, match in enumerate(story_pattern.finditer(content)):
        header = match.group(1).strip()
        story_id = (match.group(2) or match.group(3) or f"idx_{idx}").strip(". ")
        story_title = match.group(4).strip() if match.group(4) else ""
        story_body = match.group(5).strip()
        
        doc_story = f"STORY CARD: SPR_{sprint_num} - Story {story_id} ({story_title})\nFile: {filename}\nRecency Weight: {recency_weight}\n\n{story_body[:1200]}"
        
        import hashlib
        short_hash = hashlib.md5(doc_story.encode('utf-8')).hexdigest()[:6]
        chunks.append({
            "id": f"SPR_{sprint_num}_STORY_{story_id}_{short_hash}",
            "document": doc_story,
            "metadata": {
                "sprint_id": f"SPR_{sprint_num}",
                "story_id": str(story_id),
                "level": "STORY_CARD",
                "recency_weight": recency_weight,
                "source": filename,
                "type": "SPRINT_DNA"
            }
        })

    return chunks


def sync_all_sprints():
    logging.info("Starting Sprint DNA Vector Synchronization...")
    client = get_chroma_client()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    all_files = glob.glob(os.path.join(ARCHIVE_DIR, "*.md")) + glob.glob(os.path.join(ACTIVE_DIR, "*.md"))
    if not all_files:
        logging.warning("No sprint files found.")
        return

    # Find maximum sprint number
    sprint_numbers = [extract_sprint_number(os.path.basename(f)) for f in all_files]
    max_sprint = max(sprint_numbers) if sprint_numbers else 76.0
    logging.info(f"Found {len(all_files)} sprint files across active/archive. Max Sprint: SPR_{max_sprint}")

    all_chunks = []
    for fpath in all_files:
        chunks = parse_sprint_file(fpath, max_sprint)
        all_chunks.extend(chunks)

    logging.info(f"Generated {len(all_chunks)} hybrid sprint chunks. Connecting to collection '{COLLECTION_SPRINT}'...")
    
    try:
        collection = client.get_or_create_collection(name=COLLECTION_SPRINT, embedding_function=ef)
    except Exception:
        collection = client.get_or_create_collection(name=COLLECTION_SPRINT)

    # Ingest in batches of 100
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        ids = [c["id"] for c in batch]
        docs = [c["document"] for c in batch]
        metas = [c["metadata"] for c in batch]
        
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        logging.info(f"Upserted batch {i // batch_size + 1}/{(len(all_chunks) + batch_size - 1) // batch_size} ({len(batch)} chunks)")

    logging.info("✅ Sprint DNA Synchronization complete!")


if __name__ == "__main__":
    t0 = time.time()
    sync_all_sprints()
    print(f"Elapsed time: {time.time() - t0:.2f}s")
