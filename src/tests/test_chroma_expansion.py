#!/usr/bin/env python3
"""Integration test: run both indexers, then validate ChromaDB collections."""

import importlib.util
import logging
import os
import sys

import chromadb

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
FORGE_DIR = os.path.join(HERE, "..", "forge")


def _run_indexer(filename: str) -> None:
    """Import and execute a forge indexer by filename."""
    path = os.path.join(FORGE_DIR, filename)
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    if spec is None or spec.loader is None:
        print(f"FAIL: Could not load {filename}")
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


def _check(condition: bool, label: str, critical: bool = True) -> None:
    if condition:
        print(f"  PASS: {label}")
    elif critical:
        print(f"  FAIL: {label}")
        sys.exit(1)
    else:
        print(f"  WARN: {label}")


def main() -> None:
    LOG.info("Starting ChromaDB expansion integration test")

    # 1. Run indexers
    LOG.info("Running artifact indexer...")
    _run_indexer("index_artifacts_to_rag.py")

    LOG.info("Running resume indexer...")
    _run_indexer("index_resume_to_rag.py")

    # 2. Validate
    client = chromadb.HttpClient(host="127.0.0.1", port=8001)

    artifact_vault = client.get_collection("artifact_vault")
    career_ledger = client.get_collection("career_ledger")

    print("\n--- Critical Checks ---")
    _check(artifact_vault.count() > 0, "artifact_vault has entries", critical=True)
    _check(career_ledger.count() > 0, "career_ledger has entries", critical=True)

    # Check era metadata on career_ledger
    career_sample = career_ledger.get(limit=10)
    has_era = any(
        md.get("era") not in (None, "")
        for md in (career_sample.get("metadatas") or [])
    )
    _check(has_era, "at least one career entry has 'era' metadata", critical=True)

    # Check gdrive_id on artifact_vault (warning only — may be empty)
    artifact_sample = artifact_vault.get(limit=20)
    has_gdrive = any(
        md.get("gdrive_id") not in (None, "")
        for md in (artifact_sample.get("metadatas") or [])
    )
    _check(has_gdrive, "at least one artifact has 'gdrive_id' metadata", critical=False)

    print("\nAll critical checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
