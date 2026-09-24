"""
Unit Test Suite for [FEAT-597 / FEAT-582 / BKM-060]:
Draft Promotion, Safe Non-WIS ID Allocation & Background Static HTML Rebuild Trigger.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from curator.draft_decomposer import (
    promote_draft_to_db,
    _domain_source_max_id,
    _max_numeric_id
)


def test_max_numeric_id_extraction():
    """Verify numeric ID extraction from ID lists and objects."""
    cards = [
        {"id": "WIS-001"},
        {"id": "WIS-042"},
        {"id": "WIS-481"},
        {"id": "invalid"}
    ]
    assert _max_numeric_id(cards, "WIS") == 481
    assert _max_numeric_id([], "WIS") == 0


def test_domain_source_max_id_live():
    """Verify safe max ID resolution directly against authoritative lab sources."""
    bkm_max = _domain_source_max_id("BKM")
    assert bkm_max >= 60, f"Expected BKM max >= 60, got {bkm_max}"

    feat_max = _domain_source_max_id("FEAT")
    assert feat_max >= 430, f"Expected FEAT max >= 430, got {feat_max}"

    rdna_max = _domain_source_max_id("RDNA")
    assert rdna_max >= 5, f"Expected RDNA max >= 5, got {rdna_max}"

    disc_max = _domain_source_max_id("DISC")
    assert disc_max >= 10, f"Expected DISC max >= 10, got {disc_max}"


def test_promote_draft_to_db_hermetic():
    """
    Test promote_draft_to_db allocates collision-safe IDs and triggers static HTML rebuild.
    Uses temporary hermetic files to avoid touching production data files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        mock_wisdom = tmppath / "wisdom_data.json"
        mock_phl = tmppath / "philosophy_data.json"
        mock_manifest = tmppath / "dna_manifest.json"
        mock_bones = tmppath / "bone_collections.json"

        mock_wisdom.write_text("[]", encoding="utf-8")
        mock_phl.write_text("[]", encoding="utf-8")
        mock_manifest.write_text("{}", encoding="utf-8")

        mock_chunks = [
            {
                "chunk_id": "CHUNK-01",
                "proposed_domain": "BKM",
                "title": "Hermetic Test Protocol",
                "narrative": "A test operational protocol mandate.",
                "origin_verbatim": "Rule 1: Hermetic test isolation.",
                "suggested_tags": ["test", "bkm"]
            },
            {
                "chunk_id": "CHUNK-02",
                "proposed_domain": "FEAT",
                "title": "Hermetic Test Feature",
                "narrative": "A test capability spec.",
                "origin_verbatim": "Feature 1: Hermetic capabilities.",
                "suggested_tags": ["test", "feat"]
            }
        ]

        payload = {
            "chunks": mock_chunks,
            "bone_collection": {"name": "Test Track"}
        }

        with patch("curator.draft_decomposer.WISDOM_PATH", mock_wisdom), \
             patch("curator.draft_decomposer.PHILOSOPHY_PATH", mock_phl), \
             patch("curator.draft_decomposer.MANIFEST_PATH", mock_manifest), \
             patch("curator.draft_decomposer.BONE_COLLECTIONS_PATH", mock_bones), \
             patch("curator.draft_decomposer._trigger_static_html_rebuild") as mock_rebuild:

            res = promote_draft_to_db(payload)

            assert res["status"] == "success"
            assert res["promoted_count"] == 2
            assert len(res["created_ids"]) == 2

            # Confirm BKM and FEAT IDs are collision-safe (greater than live source maximums)
            bkm_id = res["created_ids"][0]
            feat_id = res["created_ids"][1]
            assert bkm_id.startswith("BKM-")
            assert int(bkm_id.split("-")[1]) > 60
            assert feat_id.startswith("FEAT-")
            assert int(feat_id.split("-")[1]) > 430

            # Verify static HTML rebuild trigger was fired
            assert mock_rebuild.called
