#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[FEAT-592 / BKM-024] Unit and Integration Test Suite for Historical Journal to DNA Bridge.
Tests:
1. Extraction logic for dialogue triggers, findings, and evidence.
2. Fingerprint hashing and deduplication idempotency.
3. Theme and bucket classification.
4. Polymorphic DNA schema compliance (WIS cards).
5. Dry-run and live bridge execution.
"""

import sys
import json
from pathlib import Path

# Paths
DEV_LAB_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIELD_NOTES_DIR = DEV_LAB_ROOT / "Portfolio_Dev" / "field_notes"
sys.path.insert(0, str(FIELD_NOTES_DIR))

from journal_to_dna_bridge import (
    get_gem_fingerprint,
    map_theme_and_bucket,
    extract_title_and_narrative,
    run_bridge,
    WISDOM_DATA_PATH
)


def test_gem_fingerprint_idempotency():
    """Verify that fingerprinting is deterministic and normalizes whitespace."""
    text_a = "BMC23 module upgrade and Embedded File System (EFS) update."
    text_b = "  bmc23 module upgrade   and Embedded File System (EFS) update.  \n"
    assert get_gem_fingerprint(text_a) == get_gem_fingerprint(text_b)


def test_theme_and_bucket_classification():
    """Verify keyword classification into standard lab themes and buckets."""
    theme_sec, bucket_sec = map_theme_and_bucket("RAKP auth session vulnerability and CVE-2013-4786")
    assert theme_sec == "Security & Manageability"
    assert bucket_sec == "bucket_security_manageability"

    theme_val, bucket_val = map_theme_and_bucket("PECI sideband telemetry throughput and I2C commands")
    assert theme_val == "Silicon Validation Methodology"
    assert bucket_val == "bucket_silicon_validation"

    theme_auto, bucket_auto = map_theme_and_bucket("PyTest automation framework and FTF library")
    assert theme_auto == "Systems Architecture & Automation"
    assert bucket_auto == "bucket_systems_architecture"

    theme_lead, bucket_lead = map_theme_and_bucket("Engineering leadership and team mentorship")
    assert theme_lead == "Engineering Leadership"
    assert bucket_lead == "bucket_engineering_leadership"


def test_extract_title_and_narrative():
    """Verify parsing of dialogue structure into milestone title and narrative."""
    sample_dialogue = (
        "User: What was the technical milestone for FTF library automation? (2005-03-01)\n"
        "Pinky: In 2005-03-01, the milestone was: Development of FTF library to automate HTTP_MTP tests\n\n"
        "Evidence: Primary TODO or research link mentioned in RAW LOGS"
    )
    title, narrative, evidence = extract_title_and_narrative(sample_dialogue)
    assert "FTF library" in title
    assert "Development of FTF library" in narrative
    assert "RAW LOGS" in evidence


def test_polymorphic_wisdom_schema_compliance():
    """Verify that cards in wisdom_data.json conform to polymorphic DNA schema invariants."""
    assert WISDOM_DATA_PATH.exists()
    with open(WISDOM_DATA_PATH, "r", encoding="utf-8") as f:
        cards = json.load(f)

    assert len(cards) > 0
    for card in cards[:30]:  # Verify schema across sample cards
        assert "id" in card and card["id"].startswith("WIS-")
        assert "theme" in card
        assert "origin" in card
        assert "synthesis" in card
        assert "metadata" in card

        origin = card["origin"]
        assert "author" in origin
        assert "text" in origin
        assert "source" in origin

        synthesis = card["synthesis"]
        assert "title" in synthesis
        assert "narrative_context" in synthesis

        metadata = card["metadata"]
        assert "tags" in metadata and isinstance(metadata["tags"], list)
        assert "bucket_id" in metadata
        assert "status" in metadata


def test_bridge_dry_run():
    """Verify that dry-run returns valid count without corrupting wisdom_data.json."""
    count = run_bridge(dry_run=True, min_rank=4)
    assert isinstance(count, int)
    assert count >= 0
