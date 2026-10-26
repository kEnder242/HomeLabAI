#!/usr/bin/env python3
"""
[FEAT-469] Index LAB_INFRASTRUCTURE.md into ChromaDB collection 'lab_infrastructure'.

Parses physical topology, hardware characteristics, transport/systemd units,
and all LAB-001..LAB-116 playbooks into discrete chunks tagged with component metadata
matching src/nodes/lab_dna_router.py.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import re
import sys

# Auto-activate venv if running under system python without chromadb
VENV_PYTHON = Path("/home/jallred/.venv/bin/python")
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import chromadb
    except ImportError:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

import chromadb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger(__name__)

DOC_PATH = Path("/home/jallred/Dev_Lab/HomeLabAI/docs/LAB_INFRASTRUCTURE.md")
CHROMA_HOST = "127.0.0.1"
CHROMA_PORT = 8001
COLLECTION_NAME = "lab_infrastructure"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of at most `size` characters with `overlap`."""
    text = text.strip()
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += (size - overlap)
    return chunks


def parse_lab_infrastructure(doc_text: str) -> list[dict]:
    """
    Parse LAB_INFRASTRUCTURE.md into structured records.
    Returns list of dicts with:
      - component: str (e.g. 'LAB-TOPOLOGY', 'LAB-001')
      - title: str
      - text: str
    """
    records: list[dict] = []

    # 1. Overview sections: Physical Storage & Systemd Topology
    overview_match = re.search(
        r"## 📍 Physical Storage & Mounts(.*?)## 🚀 Infrastructure Playbooks",
        doc_text,
        re.DOTALL,
    )
    if overview_match:
        overview_body = overview_match.group(1).strip()
        chunks = _chunk_text(overview_body)
        for i, chunk in enumerate(chunks):
            records.append({
                "component": "LAB-TOPOLOGY",
                "title": f"Physical Floor, Storage & Systemd Service Topology (Part {i + 1})",
                "text": f"Component: LAB-TOPOLOGY | Title: Physical Floor & Service Topology\n{chunk}",
                "chunk_index": i,
            })

    # 2. Playbook sections: ### LAB-XXX: <Title>
    playbook_pattern = re.compile(
        r"###\s+(LAB-\d+):\s+([^\n]+)\n(.*?)(?=\n###\s+LAB-\d+:|\Z)",
        re.DOTALL,
    )
    for comp, title, body in playbook_pattern.findall(doc_text):
        comp = comp.strip()
        title = title.strip()
        chunks = _chunk_text(body.strip())
        for i, chunk in enumerate(chunks):
            records.append({
                "component": comp,
                "title": f"{title} (Part {i + 1})" if len(chunks) > 1 else title,
                "text": f"Component: {comp} | Title: {title}\n{chunk}",
                "chunk_index": i,
            })

    return records


def index_to_chroma(records: list[dict], host: str = CHROMA_HOST, port: int = CHROMA_PORT) -> int:
    """Connect to ChromaDB and index parsed records."""
    client = chromadb.HttpClient(host=host, port=port)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for r in records:
        comp = r["component"]
        idx = r["chunk_index"]
        comp_slug = comp.lower().replace("-", "_")
        hash_suffix = hashlib.md5(r["text"].encode("utf-8")).hexdigest()[:8]
        doc_id = f"infra_{comp_slug}_{idx}_{hash_suffix}"

        ids.append(doc_id)
        documents.append(r["text"])
        metadatas.append({
            "component": comp,
            "title": r["title"],
            "category": "infrastructure",
            "source": "LAB_INFRASTRUCTURE.md",
            "chunk_index": idx,
        })

    # Upsert in batch
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    LOG.info("Successfully indexed %d records into collection '%s'.", len(ids), COLLECTION_NAME)
    return collection.count()


def main() -> None:
    if not DOC_PATH.exists():
        LOG.error("Document not found: %s", DOC_PATH)
        sys.exit(1)

    with open(DOC_PATH, "r", encoding="utf-8") as f:
        doc_text = f.read()

    records = parse_lab_infrastructure(doc_text)
    LOG.info("Parsed %d chunks from %s", len(records), DOC_PATH.name)

    total_count = index_to_chroma(records)
    LOG.info("ChromaDB collection '%s' total count is now: %d", COLLECTION_NAME, total_count)


if __name__ == "__main__":
    main()
