#!/usr/bin/env python3
"""Index career / resume data into ChromaDB collection 'career_ledger'."""

import hashlib
import json
import logging
import re
from datetime import datetime
from glob import glob

import chromadb

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

RAW_NOTES = "/home/jallred/Dev_Lab/Portfolio_Dev/raw_notes"
CV_PATH = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/cv_3x3_summary.json"
SECTION_HEADERS = re.compile(
    r"^(Summary|Experience|Technical Skills|Professional Experience|"
    r"Era\s*\d+|Education|Certifications|Leadership|Overview)$",
    re.IGNORECASE,
)
CHUNK_SIZE = 1000


def _pick_latest_resume(directory: str) -> str | None:
    """Return path to the most recent resume .txt file."""
    candidates = [p for p in glob(f"{directory}/*.txt") if "Resume" in p or "resume" in p]
    if not candidates:
        return None

    def _date_key(path: str) -> tuple[int, int]:
        """Extract (year, month) from filename for sorting."""
        base = path.rsplit("/", 1)[-1]
        for fmt in ("%b %Y", "%B %Y", "%m-%Y"):
            try:
                # Try to find a date pattern in the filename
                match = re.search(r"([A-Z][a-z]+)\s+(\d{4})", base)
                if match:
                    dt = datetime.strptime(f"{match.group(1)} {match.group(2)}", fmt)
                    return (dt.year, dt.month)
            except ValueError:
                continue
        return (0, 0)

    return max(candidates, key=_date_key)


def _parse_resume_sections(text: str) -> dict[str, str]:
    """Split resume text into sections by header."""
    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if SECTION_HEADERS.match(stripped):
            current = stripped.rstrip(":").strip()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(stripped)

    return {k: "\n".join(v) for k, v in sections.items()}


def _chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks of at most `size` characters."""
    return [text[i : i + size] for i in range(0, len(text), size)]


def main() -> None:
    client = chromadb.HttpClient(host="127.0.0.1", port=8001)
    collection = client.get_or_create_collection("career_ledger")

    # --- Resume ---
    resume_path = _pick_latest_resume(RAW_NOTES)
    if resume_path:
        LOG.info("Using resume: %s", resume_path)
        with open(resume_path) as f:
            resume_text = f.read()
        sections = _parse_resume_sections(resume_text)
        for section_name, content in sections.items():
            for i, chunk in enumerate(_chunk_text(content)):
                doc_id = f"career_{hashlib.md5(f'{section_name}_{i}'.encode()).hexdigest()}"
                if not collection.get(ids=[doc_id])["ids"]:
                    collection.add(
                        documents=[chunk],
                        metadatas=[{"era": section_name, "domain": "career_pedigree"}],
                        ids=[doc_id],
                    )
                    LOG.info("Added resume section: %s (chunk %d)", section_name, i)
                else:
                    LOG.info("Skipping duplicate: %s (chunk %d)", section_name, i)
    else:
        LOG.warning("No resume file found in %s", RAW_NOTES)

    # --- Focal goals (from cv_3x3_summary.json) ---
    try:
        with open(CV_PATH) as f:
            cv_data = json.load(f)
    except FileNotFoundError:
        LOG.warning("cv_3x3_summary.json not found — skipping focal goals")
        cv_data = None

    if cv_data and "pillars" in cv_data:
        for pillar_name, details in cv_data["pillars"].items():
            points = details.get("focal_points", [])
            text = f"{pillar_name}: {' '.join(points)}"
            doc_id = f"focal_{hashlib.md5(pillar_name.encode()).hexdigest()}"
            if not collection.get(ids=[doc_id])["ids"]:
                collection.add(
                    documents=[text],
                    metadatas=[{"era": pillar_name, "domain": "career_pedigree"}],
                    ids=[doc_id],
                )
                LOG.info("Added focal pillar: %s", pillar_name)
            else:
                LOG.info("Skipping duplicate focal pillar: %s", pillar_name)

    LOG.info("Resume / focal index complete.")


if __name__ == "__main__":
    main()
