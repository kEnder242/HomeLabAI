#!/usr/bin/env python3
"""
[FEAT-626 / FEAT-628] Sprint 95.1 -- Self-Contained Spine Manager & Document DNA
Archive: unit test suite.

Covers :class:`projection.bones.SpineManager`:
  1. Default skeleton generation and missing-spine load behaviour.
  2. Atomic save + reload round-trip of the spine JSON artifact.
  3. Version registration, idempotency, and parent lineage tracking.
  4. Topological node mapping across multiple versions with text hashing.
  5. Document DNA allocation (DOC-<paper_id>-001 stamping), quarantine, and
     retrieval.

Hermetic (BKM-024 fast path): every test uses ``tmp_path``, so no
Portfolio_Dev filesystem dependency, no network, no LLM. Silicon validation is
performed post-dispatch by the orchestrator.
"""

import hashlib
import json
import sys

import pytest

# Resolve the package regardless of the invoking rootdir.
_HOMELAB_SRC = "/home/jallred/Dev_Lab/HomeLabAI/src"
if _HOMELAB_SRC not in sys.path:
    sys.path.insert(0, _HOMELAB_SRC)

from projection.bones import (
    SPINE_SCHEMA_VERSION,
    SpineManager,
)

# --------------------------------------------------------------- schema/skeleton


def test_schema_version_constants():
    assert SpineManager.SCHEMA_VERSION == "spine.v1"
    assert SPINE_SCHEMA_VERSION == "spine.v1"
    assert SpineManager.PAPERS_DIR.as_posix() == "Portfolio_Dev/field_notes/data/papers"


def test_empty_spine_skeleton_shape():
    skeleton = SpineManager.empty_spine("RESUME")
    assert skeleton == {
        "schema": "spine.v1",
        "paper_id": "RESUME",
        "title": "",
        "versions": [],
        "topology": {},
        "document_dna": [],
    }


def test_load_spine_missing_returns_skeleton(tmp_path):
    """A fresh paper has no spine yet -- load must not raise."""
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    assert spine["schema"] == "spine.v1"
    assert spine["paper_id"] == "RESUME"
    assert spine["title"] == ""
    assert spine["versions"] == []
    assert spine["topology"] == {}
    assert spine["document_dna"] == []


def test_load_spine_preserves_title(tmp_path):
    spine = SpineManager.load_spine("PAPER-A", base_dir=tmp_path)
    spine["title"] = "A Retained Title"
    SpineManager.save_spine("PAPER-A", spine, base_dir=tmp_path)

    reloaded = SpineManager.load_spine("PAPER-A", base_dir=tmp_path)
    assert reloaded["title"] == "A Retained Title"


def test_spine_path_naming_convention(tmp_path):
    path = SpineManager.spine_path("RESUME", base_dir=tmp_path)
    assert path.name == "PAPER-RESUME_spine.json"
    assert path.parent == tmp_path


# ------------------------------------------------------------- atomic save/load


def test_save_spine_creates_file_and_returns_path(tmp_path):
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    written = SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)

    assert written.exists()
    assert written == tmp_path / "PAPER-RESUME_spine.json"


def test_save_spine_writes_indent_two_json(tmp_path):
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json", description="baseline")

    written = SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)
    raw = written.read_text(encoding="utf-8")

    # indent=2 is part of the contract (human-readable, self-contained artifact).
    assert '\n  "schema"' in raw
    assert '\n  "paper_id"' in raw

    parsed = json.loads(raw)
    assert parsed["schema"] == "spine.v1"
    assert parsed["versions"][0]["version_id"] == "v1"


def test_save_spine_is_atomic_no_tmp_residue(tmp_path):
    """os.replace(tmp, final) must leave no .tmp file behind."""
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)

    assert list(tmp_path.glob("*.tmp")) == []


def test_save_spine_creates_missing_parent_dirs(tmp_path):
    nested = tmp_path / "deep" / "nested" / "papers"
    spine = SpineManager.load_spine("RESUME", base_dir=nested)
    written = SpineManager.save_spine("RESUME", spine, base_dir=nested)
    assert written.exists()


def test_save_then_load_round_trip_preserves_all_sections(tmp_path):
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")
    SpineManager.register_version(spine, "v2", "PAPER-RESUME_v2.json", parent_version="v1")
    SpineManager.map_node(spine, "node_1", "v2", "sec_summary", block_id="b0", text="hello world")
    doc_id = SpineManager.add_document_dna(spine, "resilience", "Bounce-back", "text body", "node_1")

    SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)
    reloaded = SpineManager.load_spine("RESUME", base_dir=tmp_path)

    assert len(reloaded["versions"]) == 2
    assert reloaded["topology"]["node_1"]["versions"]["v2"]["section_id"] == "sec_summary"
    assert SpineManager.get_document_dna(reloaded, doc_id) is not None


def test_save_spine_stamps_schema_and_paper_id(tmp_path):
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    spine["schema"] = "TAMPERED"
    spine["paper_id"] = "WRONG"

    SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)
    reloaded = SpineManager.load_spine("RESUME", base_dir=tmp_path)

    assert reloaded["schema"] == "spine.v1"
    assert reloaded["paper_id"] == "RESUME"


def test_save_spine_accepts_str_base_dir(tmp_path):
    spine = SpineManager.load_spine("RESUME", base_dir=str(tmp_path))
    written = SpineManager.save_spine("RESUME", spine, base_dir=str(tmp_path))
    assert written.exists()


def test_load_spine_rejects_non_object_json(tmp_path):
    path = SpineManager.spine_path("BROKEN", base_dir=tmp_path)
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(TypeError):
        SpineManager.load_spine("BROKEN", base_dir=tmp_path)


# ---------------------------------------------------------- version registration


def test_register_version_appends_entry():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")

    assert len(spine["versions"]) == 1
    entry = spine["versions"][0]
    assert entry["version_id"] == "v1"
    assert entry["filename"] == "PAPER-RESUME_v1.json"
    assert entry["parent_version"] is None
    assert entry["description"] == ""
    assert "registered_at" in entry


def test_register_version_is_idempotent():
    """BKM-070: re-anchoring, not serial compounding."""
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")
    SpineManager.register_version(spine, "v1", "DIFFERENT.json")

    assert len(spine["versions"]) == 1
    assert spine["versions"][0]["filename"] == "PAPER-RESUME_v1.json"


def test_register_version_lineage_tracking():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json", description="baseline")
    SpineManager.register_version(spine, "v2", "PAPER-RESUME_v2.json", parent_version="v1")
    SpineManager.register_version(spine, "v3", "PAPER-RESUME_v3.json", parent_version="v2")

    parents = {v["version_id"]: v["parent_version"] for v in spine["versions"]}
    assert parents == {"v1": None, "v2": "v1", "v3": "v2"}


def test_register_version_returns_spine():
    spine = SpineManager.empty_spine("RESUME")
    returned = SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")
    assert returned is spine


def test_register_version_timestamps_are_iso8601():
    from datetime import datetime

    spine = SpineManager.empty_spine("RESUME")
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")

    stamp = spine["versions"][0]["registered_at"]
    assert datetime.fromisoformat(stamp) is not None


# ------------------------------------------------------------- topology mapping


def test_map_node_creates_node_and_version_entry():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.map_node(spine, "node_1", "v1", "sec_summary")

    node = spine["topology"]["node_1"]
    assert node["node_id"] == "node_1"
    assert node["versions"]["v1"]["section_id"] == "sec_summary"
    assert node["versions"]["v1"]["block_id"] == ""
    assert node["versions"]["v1"]["role"] == ""


def test_map_node_computes_text_hash():
    spine = SpineManager.empty_spine("RESUME")
    text = "Resilience is a re-anchoring, not a compounding."
    SpineManager.map_node(spine, "node_1", "v1", "sec_summary", text=text)

    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    node = spine["topology"]["node_1"]["versions"]["v1"]
    assert node["text_hash"] == expected
    assert len(node["text_hash"]) == 16


def test_map_node_without_text_yields_empty_hash():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.map_node(spine, "node_1", "v1", "sec_summary")
    assert spine["topology"]["node_1"]["versions"]["v1"]["text_hash"] == ""


def test_map_node_distinguishes_changed_text_across_versions():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.map_node(spine, "node_1", "v1", "sec_summary", text="original prose")
    SpineManager.map_node(spine, "node_1", "v2", "sec_summary", text="revised prose")

    v1 = spine["topology"]["node_1"]["versions"]["v1"]
    v2 = spine["topology"]["node_1"]["versions"]["v2"]
    assert v1["text_hash"] != v2["text_hash"]


def test_map_node_across_multiple_versions_preserves_history():
    spine = SpineManager.empty_spine("RESUME")
    for version in ("v1", "v2", "v3"):
        SpineManager.map_node(spine, "node_1", version, f"sec_{version}", text=f"body {version}")

    versions = spine["topology"]["node_1"]["versions"]
    assert set(versions) == {"v1", "v2", "v3"}
    assert versions["v2"]["section_id"] == "sec_v2"


def test_map_node_multiple_distinct_nodes():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.map_node(spine, "node_1", "v1", "sec_a")
    SpineManager.map_node(spine, "node_2", "v1", "sec_b")

    assert set(spine["topology"]) == {"node_1", "node_2"}


def test_map_node_returns_spine():
    spine = SpineManager.empty_spine("RESUME")
    assert SpineManager.map_node(spine, "node_1", "v1", "sec_a") is spine


def test_map_node_remap_same_version_is_idempotent():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.map_node(spine, "node_1", "v1", "sec_a", text="same")
    SpineManager.map_node(spine, "node_1", "v1", "sec_a", text="same")

    assert len(spine["topology"]["node_1"]["versions"]) == 1


# ------------------------------------------------------------- document DNA


def test_add_document_dna_first_id_is_001():
    spine = SpineManager.empty_spine("RESUME")
    doc_id = SpineManager.add_document_dna(spine, "theme-a", "Title A", "text body")
    assert doc_id == "DOC-RESUME-001"


def test_add_document_dna_increments_index():
    spine = SpineManager.empty_spine("RESUME")
    first = SpineManager.add_document_dna(spine, "t", "A", "a")
    second = SpineManager.add_document_dna(spine, "t", "B", "b")
    third = SpineManager.add_document_dna(spine, "t", "C", "c")

    assert (first, second, third) == ("DOC-RESUME-001", "DOC-RESUME-002", "DOC-RESUME-003")
    assert len(spine["document_dna"]) == 3


def test_add_document_dna_record_shape():
    spine = SpineManager.empty_spine("RESUME")
    doc_id = SpineManager.add_document_dna(
        spine, "systems", "Re-Anchoring Law", "Bones are immutable.", origin_node_id="node_7"
    )

    record = spine["document_dna"][0]
    assert record["doc_dna_id"] == doc_id
    assert record["theme"] == "systems"
    assert record["title"] == "Re-Anchoring Law"
    assert record["text"] == "Bones are immutable."
    assert record["origin_node_id"] == "node_7"
    assert "extracted_at" in record


def test_add_document_dna_defaults_origin_node_empty():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.add_document_dna(spine, "t", "T", "body")
    assert spine["document_dna"][0]["origin_node_id"] == ""


def test_add_document_dna_is_quarantined():
    """FEAT-628 / BKM-060: document DNA never self-promotes to global lab DNA."""
    spine = SpineManager.empty_spine("RESUME")
    for _ in range(3):
        SpineManager.add_document_dna(spine, "t", "T", "body")

    assert all(r["promoted_to_global"] is None for r in spine["document_dna"])


def test_get_document_dna_retrieval():
    spine = SpineManager.empty_spine("RESUME")
    first = SpineManager.add_document_dna(spine, "t1", "First", "body one")
    SpineManager.add_document_dna(spine, "t2", "Second", "body two")

    record = SpineManager.get_document_dna(spine, first)
    assert record is not None
    assert record["title"] == "First"
    assert record["theme"] == "t1"


def test_get_document_dna_missing_returns_none():
    spine = SpineManager.empty_spine("RESUME")
    SpineManager.add_document_dna(spine, "t", "T", "body")
    assert SpineManager.get_document_dna(spine, "DOC-RESUME-999") is None


def test_get_document_dna_on_empty_spine_returns_none():
    assert SpineManager.get_document_dna(SpineManager.empty_spine("RESUME"), "DOC-RESUME-001") is None


def test_get_document_dna_returns_live_reference():
    """Promotion (Story 95.6) mutates in place through the returned handle."""
    spine = SpineManager.empty_spine("RESUME")
    doc_id = SpineManager.add_document_dna(spine, "t", "T", "body")

    record = SpineManager.get_document_dna(spine, doc_id)
    assert record is not None
    record["promoted_to_global"] = "WIS-999"

    promoted = SpineManager.get_document_dna(spine, doc_id)
    assert promoted is not None
    assert promoted["promoted_to_global"] == "WIS-999"


# --------------------------------------------------------- resilience / integrity


def test_load_spine_repairs_partial_containers(tmp_path):
    """A hand-edited spine missing containers must not crash the mutators."""
    SpineManager.spine_path("RESUME", base_dir=tmp_path).write_text(
        json.dumps({"schema": "spine.v1", "paper_id": "RESUME", "title": "T"}),
        encoding="utf-8",
    )

    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    assert spine["versions"] == []
    assert spine["topology"] == {}
    assert spine["document_dna"] == []

    # Mutators must work on the repaired skeleton.
    SpineManager.register_version(spine, "v1", "PAPER-RESUME_v1.json")
    SpineManager.map_node(spine, "n", "v1", "s")
    SpineManager.add_document_dna(spine, "t", "T", "b")
    assert len(spine["versions"]) == 1


def test_load_spine_preserves_unknown_keys(tmp_path):
    SpineManager.spine_path("RESUME", base_dir=tmp_path).write_text(
        json.dumps({"schema": "spine.v1", "paper_id": "RESUME", "custom_field": 42}),
        encoding="utf-8",
    )
    assert SpineManager.load_spine("RESUME", base_dir=tmp_path)["custom_field"] == 42


def test_multiple_papers_are_isolated(tmp_path):
    """Two spines in one directory must not bleed into each other."""
    resume = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    research = SpineManager.load_spine("RESEARCH", base_dir=tmp_path)

    SpineManager.register_version(resume, "v1", "PAPER-RESUME_v1.json")
    SpineManager.save_spine("RESUME", resume, base_dir=tmp_path)
    SpineManager.save_spine("RESEARCH", research, base_dir=tmp_path)

    assert len(SpineManager.load_spine("RESUME", base_dir=tmp_path)["versions"]) == 1
    assert len(SpineManager.load_spine("RESEARCH", base_dir=tmp_path)["versions"]) == 0


def test_document_dna_ids_use_owning_paper_id(tmp_path):
    spine = SpineManager.load_spine("RESEARCH", base_dir=tmp_path)
    doc_id = SpineManager.add_document_dna(spine, "t", "T", "body")
    assert doc_id == "DOC-RESEARCH-001"


def test_full_lifecycle_end_to_end(tmp_path):
    """Story 95.1 success criteria: version indexing + document_dna together."""
    spine = SpineManager.load_spine("RESUME", base_dir=tmp_path)
    SpineManager.register_version(spine, "v1_baseline", "PAPER-RESUME_v1.json", description="baseline")
    SpineManager.register_version(
        spine, "v2_annotated", "PAPER-RESUME_v2.json", parent_version="v1_baseline"
    )
    SpineManager.map_node(spine, "sec_summary", "v2_annotated", "sec_summary", text="Summary prose")
    doc_id = SpineManager.add_document_dna(
        spine, "architecture", "Spine Vault", "The spine is the manifest.", "sec_summary"
    )

    SpineManager.save_spine("RESUME", spine, base_dir=tmp_path)
    final = SpineManager.load_spine("RESUME", base_dir=tmp_path)

    assert len(final["versions"]) == 2
    assert final["topology"]["sec_summary"]["versions"]["v2_annotated"]["text_hash"]
    record = SpineManager.get_document_dna(final, doc_id)
    assert record is not None
    assert record["promoted_to_global"] is None
