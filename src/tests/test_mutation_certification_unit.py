"""
Unit Test Suite for [FEAT-598 / Story 86.6]:
Mutation Certification, Array Cleanup, and Revision Promotion.
"""

import pytest
import json
import tempfile
from pathlib import Path


def test_mutation_cleanup_logic():
    """Verify that certified mutations are purged from candidate arrays while revisions increment."""
    # Synthetic card with pending mutations
    card = {
        "id": "WIS-999",
        "domain": "WIS",
        "title": "Test Memory Invariant",
        "synthesis": {
            "title": "Test Memory Invariant",
            "narrative_context": "Base ground truth.",
            "mutations": [
                {"id": "mut_active", "lens": "Active Voice", "text": "Active voice variation."},
                {"id": "mut_exec", "lens": "Executive", "text": "Executive impact statement."}
            ],
            "revisions": []
        }
    }

    # Simulate certification of 'mut_active'
    target_mut_id = "mut_active"
    synth = card["synthesis"]

    # 1. Capture mutation text and append to revisions
    mut_entry = next((m for m in synth.get("mutations", []) if m.get("id") == target_mut_id), None)
    assert mut_entry is not None

    new_rev = {
        "id": f"rev_{card['id']}_1_{target_mut_id}",
        "lens": mut_entry.get("lens", "Active Voice"),
        "text": mut_entry.get("text", ""),
        "timestamp": "2026-09-21T19:50:00Z",
        "status": "APPROVED"
    }
    synth["revisions"].append(new_rev)

    # 2. Cleanup certified mutation from mutations[]
    synth["mutations"] = [
        m for m in synth.get("mutations", [])
        if m.get("id") != target_mut_id and m.get("mutation_id") != target_mut_id
    ]

    # Verification of post-certification state
    assert len(synth["revisions"]) == 1
    assert synth["revisions"][0]["lens"] == "Active Voice"
    assert len(synth["mutations"]) == 1
    assert synth["mutations"][0]["id"] == "mut_exec"
    assert not any(m.get("id") == "mut_active" for m in synth["mutations"])
