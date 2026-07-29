#!/usr/bin/env python3
"""Index artifact entries from field_notes into ChromaDB collection 'artifact_vault'."""

import hashlib
import json
import logging
from glob import glob

import chromadb

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

SEARCH_INDEX = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/search_index.json"
ARTIFACTS_GLOB = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/artifacts_*.json"


def _load_artifacts() -> list[dict]:
    """Load all artifact entries from artifacts_*.json files."""
    entries = []
    for path in glob(ARTIFACTS_GLOB):
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            entries.extend(data)
    return entries


def main() -> None:
    client = chromadb.HttpClient(host="127.0.0.1", port=8001)
    collection = client.get_or_create_collection("artifact_vault")

    # Load tag -> slug index
    with open(SEARCH_INDEX) as f:
        index: dict[str, list[str]] = json.load(f)

    # Invert: slug -> [tags]
    slug_to_tags: dict[str, list[str]] = {}
    for tag, slugs in index.items():
        for slug in slugs:
            slug_to_tags.setdefault(slug, []).append(tag)

    artifacts = _load_artifacts()

    for slug, tags in slug_to_tags.items():
        # Find matching artifact entry
        found = None
        for entry in artifacts:
            if slug in (entry.get("filename", ""), *entry.get("keywords", [])):
                found = entry
                break

        title = found["filename"] if found else slug
        synopsis = found.get("synopsis", "") if found else ""
        category = found.get("category", "uncategorized") if found else "uncategorized"
        gdrive_id = found.get("drive_id", found.get("gdrive_id", "")) if found else ""

        text = (
            f"Title: {title} | Synopsis: {synopsis} | "
            f"Category: {category} | Tags: {', '.join(tags)}"
        )
        metadata = {
            "title": title,
            "category": category,
            "gdrive_id": gdrive_id,
            "type": "artifact",
        }
        doc_id = f"artifact_{hashlib.md5(slug.encode()).hexdigest()}"

        if collection.get(ids=[doc_id])["ids"]:
            LOG.info("Skipping duplicate: %s", slug)
        else:
            collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
            LOG.info("Added: %s", slug)

    LOG.info("Artifact index complete. Total unique slugs: %d", len(slug_to_tags))


if __name__ == "__main__":
    main()
