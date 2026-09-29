#!/usr/bin/env python3
"""
[FEAT-603] Projection Bones: Generic Document AST, Revision Tagging & Reconciliation
Consolidated from HomeLabAI/src/curator/lens_service.py (grade_paper AST traversal)
and HomeLabAI/src/forge/refine_bones.py (revision tagging).

Architectural mandates honoured here:
  * BKM-070 (Re-Anchoring Law): bones are immutable, deterministic structural
    anchors derived from a certified document AST. Every projection reads from
    ``pi(C)``; serial compounding chains are forbidden.
  * BKM-015: structural invariants are enforced via deterministic AST/JSON
    traversal. Regex is used ONLY for deterministic ASCII token extraction
    (the bone checksum), never for semantic grading.
  * Class 1 design: zero third-party dependencies, no network, no filesystem
    side effects. Pure structural operators that both the CLI and the web
    endpoints can call.

Canonical schema (Paper AST v2 normalized)::

    {
      "paper_id": "PAPER-RESUME",
      "title": "Jason Allred - Technical Resume & CV",
      "sections": [
        {
          "id": "sec_summary",
          "heading": "Professional Summary",
          "paragraphs": ["..."],
          "citations": ["FEAT-622"],
          "review_flags": []
        }
      ],
      "metadata": {"revision_id": "v1_baseline"}
    }
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "BONE_SCHEMA_VERSION",
    "SPINE_SCHEMA_VERSION",
    "DocumentAST",
    "DocumentNode",
    "SpineManager",
    "extract_bones",
    "normalize_ast",
    "reconcile_diff",
]

# Bumped when the bone payload shape changes. Consumers (WIS/BKM) pin this.
BONE_SCHEMA_VERSION = "bones.v2"

# BKM-015: regex is scoped strictly to deterministic ASCII token extraction
# for the content checksum. It performs NO semantic judgement.
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class DocumentNode:
    """A single addressable section of a projected document.

    ``review_flags`` is the attachment point for rubric violations produced by
    :meth:`projection.engine.ProjectionEngine.project`. Flags are append-only
    dicts so that a re-projection never silently discards prior review state.
    """

    id: str
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    review_flags: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "heading": self.heading,
            "paragraphs": list(self.paragraphs),
            "citations": list(self.citations),
            "review_flags": [dict(f) for f in self.review_flags],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocumentNode:
        return cls(
            id=str(d.get("id", d.get("section_id", ""))),
            heading=str(d.get("heading", "")),
            paragraphs=[str(p) for p in d.get("paragraphs", []) if p is not None],
            citations=[str(c) for c in d.get("citations", []) if c is not None],
            review_flags=[dict(f) for f in d.get("review_flags", []) if isinstance(f, dict)],
        )

    def checksum(self) -> str:
        """Deterministic content checksum, insensitive to key ordering."""
        payload = "|".join(_ASCII_TOKEN_RE.findall(" ".join(self.paragraphs).lower()))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class DocumentAST:
    """The certified document root every projection anchors against."""

    paper_id: str
    title: str
    sections: list[DocumentNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "sections": [s.to_dict() for s in self.sections],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocumentAST:
        sections = []
        for raw in d.get("sections", []) or []:
            if isinstance(raw, DocumentNode):
                sections.append(raw)
            elif isinstance(raw, dict):
                sections.append(DocumentNode.from_dict(raw))
        return cls(
            paper_id=str(d.get("paper_id", "")),
            title=str(d.get("title", "")),
            sections=sections,
            metadata=dict(d.get("metadata", {}) or {}),
        )


def _flatten_legacy_node(node: dict[str, Any]) -> tuple[str, list[str], list[str], list[dict]]:
    """Absorb the Paper AST v1/v2 node shape used by ``lens_service.grade_paper``.

    v1/v2 nodes carry ``text`` (singular) and may live under a section's
    ``nodes`` list, or nested inside ``roles[].bullets[]`` for experience
    sections. BKM-070 forbids dropping those bones during consolidation, so
    they are flattened into (id, paragraphs, citations, flags) here.
    """
    node_id = str(node.get("node_id", node.get("id", "")))
    text = node.get("text", "")
    paragraphs = [str(p) for p in text.split("\n") if str(p).strip()] if text else []
    citations = [str(c) for c in node.get("citations", []) or []]
    flags = [dict(f) for f in node.get("review_flags", []) or [] if isinstance(f, dict)]
    return node_id, paragraphs, citations, flags


def _normalize_section(raw: Any, index: int) -> DocumentNode | None:
    if isinstance(raw, DocumentNode):
        return raw
    if not isinstance(raw, dict):
        return None

    section_id = str(raw.get("section_id", raw.get("id", f"sec_{index:02d}")))
    heading = str(raw.get("heading", ""))

    paragraphs: list[str] = []
    citations: list[str] = []
    flags: list[dict] = []

    # Already-canonical node: carry it through untouched.
    if "paragraphs" in raw:
        node = DocumentNode.from_dict(raw)
        node.id = node.id or section_id
        return node

    # Paper AST v1/v2: section-level `nodes[]`.
    for child in raw.get("nodes", []) or []:
        _, para, cite, flag = _flatten_legacy_node(child)
        paragraphs.extend(para)
        citations.extend(cite)
        flags.extend(flag)

    # Paper AST v1/v2: experience `roles[].bullets[]`.
    for role in raw.get("roles", []) or []:
        role_id = str(role.get("role_id", ""))
        context_line = str(role.get("context_line", "")).strip()
        if context_line:
            paragraphs.append(context_line)
        flags.extend(f for f in role.get("review_flags", []) or [] if isinstance(f, dict))
        for bullet in role.get("bullets", []) or []:
            bid, bpara, bcite, bflag = _flatten_legacy_node(bullet)
            if bpara:
                paragraphs.append(f"[{bid or role_id}] {bpara[0]}")
            citations.extend(bcite)
            flags.extend(bflag)

    return DocumentNode(
        id=section_id,
        heading=heading,
        paragraphs=paragraphs,
        citations=citations,
        review_flags=flags,
    )


def normalize_ast(doc: DocumentAST | dict[str, Any]) -> DocumentAST:
    """Coerce ``DocumentAST`` or any paper-AST dict variant into canonical form.

    Preserves unrecognized top-level keys (author, contact, style_schema_ref)
    under ``metadata`` so consolidation is lossless.
    """
    if isinstance(doc, DocumentAST):
        return doc
    if not isinstance(doc, dict):
        raise TypeError(f"normalize_ast expects DocumentAST or dict, got {type(doc)}")

    known = {"paper_id", "title", "sections", "metadata"}
    metadata = dict(doc.get("metadata", {}) or {})
    for key, value in doc.items():
        if key not in known:
            metadata[key] = value

    sections = []
    for index, raw in enumerate(doc.get("sections", []) or []):
        node = _normalize_section(raw, index)
        if node is not None:
            sections.append(node)

    return DocumentAST(
        paper_id=str(doc.get("paper_id", "")),
        title=str(doc.get("title", "")),
        sections=sections,
        metadata=metadata,
    )


def extract_bones(doc: DocumentAST | dict[str, Any]) -> list[dict[str, Any]]:
    """Derive immutable bone anchors from a certified document AST (BKM-070).

    Each bone is a flat, JSON-serializable structural anchor. The checksum is
    content-only, so re-projection with new review flags does not invalidate
    the bone identity -- this is what keeps diamonds (re-anchoring) legal while
    serial compounding chains remain forbidden.
    """
    ast = normalize_ast(doc)
    bones: list[dict[str, Any]] = []

    for position, node in enumerate(ast.sections):
        bone_body = {
            "schema": BONE_SCHEMA_VERSION,
            "paper_id": ast.paper_id,
            "bone_id": f"{ast.paper_id}::{node.id}" if ast.paper_id else node.id,
            "section_id": node.id,
            "position": position,
            "heading": node.heading,
            "paragraphs": list(node.paragraphs),
            "citations": list(node.citations),
            "review_flags": [dict(f) for f in node.review_flags],
        }
        # `anchor_checksum` covers structural identity only; `content_checksum`
        # covers prose. Callers reconcile on `bone_id`.
        bone_body["anchor_checksum"] = hashlib.sha256(
            json.dumps(
                {k: bone_body[k] for k in ("schema", "paper_id", "section_id", "position")},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]
        bone_body["content_checksum"] = node.checksum()
        bones.append(bone_body)

    return bones


def _index(payload: dict[str, Any] | Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Accept either a bone list or an AST dict and return a bone_id -> bone map."""
    if isinstance(payload, dict) and "bones" in payload:
        items = payload["bones"]
    elif isinstance(payload, dict) and "sections" in payload:
        items = extract_bones(payload)
    elif isinstance(payload, dict):
        # A single bone, or a bone-shaped node.
        items = [payload]
    else:
        items = list(payload or [])

    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("bone_id") or item.get("section_id") or item.get("id") or "")
        if key:
            index[key] = item
    return index


def reconcile_diff(orig: dict, revised: dict) -> dict:
    """Reconciliation operator ($M$ join, deferred per sprint notes) over bones.

    Operates structurally on bone identities: which anchors were added,
    removed, or modified, plus a bounded drift metric in ``[0.0, 1.0]``.

    Drift is ``modified / union`` -- 0.0 means the revisions are identical in
    bone composition, 1.0 means every anchor in the union changed or vanished.
    """
    orig_index = _index(orig)
    revised_index = _index(revised)

    orig_ids = set(orig_index)
    revised_ids = set(revised_index)

    added = sorted(revised_ids - orig_ids)
    removed = sorted(orig_ids - revised_ids)

    modified: list[dict[str, Any]] = []
    # Flag deltas are tracked independently of prose drift: attaching review
    # flags to an unchanged bone is a meaningful revision even though the
    # content checksum is stable.
    flag_deltas: list[dict[str, Any]] = []
    for bone_id in sorted(orig_ids & revised_ids):
        before, after = orig_index[bone_id], revised_index[bone_id]
        before_flags = _flag_ids(before)
        after_flags = _flag_ids(after)
        added_flags = sorted(after_flags - before_flags)
        resolved_flags = sorted(before_flags - after_flags)

        if added_flags or resolved_flags:
            flag_deltas.append(
                {
                    "bone_id": bone_id,
                    "flags_added": added_flags,
                    "flags_resolved": resolved_flags,
                }
            )

        if before.get("content_checksum") == after.get("content_checksum"):
            continue

        modified.append(
            {
                "bone_id": bone_id,
                "heading": after.get("heading", before.get("heading", "")),
                "content_checksum_before": before.get("content_checksum"),
                "content_checksum_after": after.get("content_checksum"),
                "flags_added": added_flags,
                "flags_resolved": resolved_flags,
            }
        )

    modified_ids = [m["bone_id"] for m in modified]
    union = orig_ids | revised_ids
    # Drift covers the full structural delta. A pure addition or removal is
    # just as much a revision as an in-place modification, so all three are
    # counted against the union of bone identities.
    changed_ids = set(added) | set(removed) | set(modified_ids)
    drift = round(len(changed_ids) / len(union), 6) if union else 0.0
    flag_drift = round(len(flag_deltas) / len(union), 6) if union else 0.0

    return {
        "status": "success",
        "schema": BONE_SCHEMA_VERSION,
        "added": added,
        "removed": removed,
        "modified": modified,
        "flag_deltas": flag_deltas,
        "flags_added_total": sum(len(d["flags_added"]) for d in flag_deltas),
        "flags_resolved_total": sum(len(d["flags_resolved"]) for d in flag_deltas),
        "unchanged_count": len((orig_ids & revised_ids) - set(modified_ids)),
        "orig_count": len(orig_ids),
        "revised_count": len(revised_ids),
        "drift": drift,
        "flag_drift": flag_drift,
        "is_reconciled": not added and not removed and not modified and not flag_deltas,
    }


def _flag_ids(bone: dict[str, Any]) -> set[str]:
    return {
        str(f.get("id") or f.get("rule_id"))
        for f in bone.get("review_flags", []) or []
        if isinstance(f, dict)
    }


def _utc_now_iso() -> str:
    """Timezone-aware UTC stamp used by every spine mutation."""
    return datetime.now(timezone.utc).isoformat()


# Bumped when the spine payload shape changes. Distinct from BONE_SCHEMA_VERSION:
# bones are per-section structural anchors, the spine is the per-paper manifest.
SPINE_SCHEMA_VERSION = "spine.v1"


class SpineManager:
    """[FEAT-626 / FEAT-628] Self-contained spine manifest & document DNA vault.

    The spine (``PAPER-<paper_id>_spine.json``) is the single authoritative index
    for a paper's version lineage, topological node mapping, and the
    document-scoped DNA archive. It is a *self-contained* artifact (BKM-073 /
    INS-041): every mutation is expressed as a plain-dict operation against a
    spine dict that is written out in full, so no runtime reconstitution engine
    or sparse micro-file is ever required to recover state.

    Three invariants are enforced here:

    1. **Lineage uniqueness (BKM-070 re-anchoring).** ``register_version`` is
       idempotent per ``version_id`` -- re-registering an existing version never
       forks the lineage or duplicates history.
    2. **Content addressing.** ``map_node`` stores a ``text_hash`` rather than
       raw prose, so topology stays an index of *where* content lives without
       duplicating the self-contained version files.
    3. **Quarantine gate (FEAT-628 / BKM-060).** ``add_document_dna`` stamps
       every record ``promoted_to_global=None``. Document-scoped DNA never
       reaches global lab DNA (WIS/INS) implicitly; promotion is an explicit,
       separately-certified act (Story 95.6).

    Persistence is atomic (``.tmp`` + :func:`os.replace`) per the Class 1
    Atomic Reliability mandate, so a crashed write can never leave a torn spine.
    """

    SCHEMA_VERSION = SPINE_SCHEMA_VERSION

    #: Default archive root for self-contained paper versions and their spines.
    PAPERS_DIR = Path("Portfolio_Dev/field_notes/data/papers")

    # ------------------------------------------------------------------ paths

    @classmethod
    def spine_path(cls, paper_id: str, base_dir: Path | str | None = None) -> Path:
        """Resolve the absolute-or-relative spine path for ``paper_id``."""
        root = cls.PAPERS_DIR if base_dir is None else Path(base_dir)
        return Path(root) / f"PAPER-{paper_id}_spine.json"

    # ------------------------------------------------------------- persistence

    @classmethod
    def load_spine(cls, paper_id: str, base_dir: Path | str | None = None) -> dict[str, Any]:
        """Load the spine for ``paper_id``, or return a valid empty skeleton.

        A missing spine is not an error: a fresh paper legitimately has no
        history yet, and the caller must be able to ``register_version`` against
        a skeleton without a bootstrap write. The skeleton always carries the
        canonical ``SCHEMA_VERSION`` so a first save is already conformant.
        """
        path = cls.spine_path(paper_id, base_dir)
        if not path.exists():
            return cls.empty_spine(paper_id)

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise TypeError(f"Spine at {path} is not a JSON object: {type(data)}")

        # Tolerate hand-edited / partial spines by re-asserting the container
        # types the mutators below rely on. Unknown keys are preserved.
        data.setdefault("schema", cls.SCHEMA_VERSION)
        data["paper_id"] = str(data.get("paper_id") or paper_id)
        if not isinstance(data.get("versions"), list):
            data["versions"] = []
        if not isinstance(data.get("topology"), dict):
            data["topology"] = {}
        if not isinstance(data.get("document_dna"), list):
            data["document_dna"] = []
        return data

    @classmethod
    def save_spine(
        cls,
        paper_id: str,
        data: dict[str, Any],
        base_dir: Path | str | None = None,
    ) -> Path:
        """Atomically persist ``data`` as the spine for ``paper_id``.

        Returns the written path. The ``.tmp`` + :func:`os.replace` sequence
        guarantees a reader never observes a half-written spine.
        """
        path = cls.spine_path(paper_id, base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = dict(data)
        payload["schema"] = cls.SCHEMA_VERSION
        payload["paper_id"] = str(paper_id)

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
            handle.write("\n")
        os.replace(tmp_path, path)
        return path

    @classmethod
    def empty_spine(cls, paper_id: str) -> dict[str, Any]:
        """Return the canonical zero-state spine skeleton for ``paper_id``."""
        return {
            "schema": cls.SCHEMA_VERSION,
            "paper_id": str(paper_id),
            "title": "",
            "versions": [],
            "topology": {},
            "document_dna": [],
        }

    # -------------------------------------------------------------- versioning

    @staticmethod
    def register_version(
        spine_data: dict[str, Any],
        version_id: str,
        filename: str,
        parent_version: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Register a document version in the lineage. Idempotent per version_id.

        Re-registering an existing ``version_id`` is a no-op that still returns
        the mutated spine, so replaying an ingest is safe (BKM-070: re-anchoring,
        never serial compounding).
        """
        versions = spine_data.setdefault("versions", [])
        if any(str(v.get("version_id")) == str(version_id) for v in versions if isinstance(v, dict)):
            return spine_data

        versions.append(
            {
                "version_id": str(version_id),
                "filename": str(filename),
                "parent_version": str(parent_version) if parent_version else None,
                "description": str(description or ""),
                "registered_at": _utc_now_iso(),
            }
        )
        return spine_data

    @staticmethod
    def map_node(
        spine_data: dict[str, Any],
        node_id: str,
        version_id: str,
        section_id: str,
        block_id: str = "",
        role: str = "",
        text: str = "",
    ) -> dict[str, Any]:
        """Map a topological node to a ``(section, block)`` pair within a version.

        Stores a ``text_hash`` (16-hex sha256 prefix) instead of the raw prose:
        the self-contained version file already owns the text, and duplicating it
        here would let the two drift. An empty ``text`` yields an empty hash so
        a purely positional mapping stays explicit.
        """
        text_hash = ""
        if text:
            text_hash = hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]

        topology = spine_data.setdefault("topology", {})
        node = topology.setdefault(str(node_id), {})
        node.setdefault("node_id", str(node_id))
        node.setdefault("versions", {})
        node["versions"][str(version_id)] = {
            "version_id": str(version_id),
            "section_id": str(section_id),
            "block_id": str(block_id or ""),
            "role": str(role or ""),
            "text_hash": text_hash,
        }
        return spine_data

    # ------------------------------------------------------- document DNA vault

    @staticmethod
    def add_document_dna(
        spine_data: dict[str, Any],
        theme: str,
        title: str,
        text: str,
        origin_node_id: str = "",
    ) -> str:
        """Add a document-scoped DNA record and return its allocated ID.

        IDs are ``DOC-<paper_id>-<NNN>`` with a zero-padded sequential index
        derived from the current record count. Every record is stamped
        ``promoted_to_global=None`` -- document DNA is quarantined (FEAT-628)
        until an explicit certified promotion flips that field.
        """
        archive = spine_data.setdefault("document_dna", [])
        index = len(archive) + 1
        paper_id = str(spine_data.get("paper_id", ""))
        doc_dna_id = f"DOC-{paper_id}-{index:03d}"

        archive.append(
            {
                "doc_dna_id": doc_dna_id,
                "theme": str(theme or ""),
                "title": str(title or ""),
                "text": str(text or ""),
                "origin_node_id": str(origin_node_id or ""),
                "promoted_to_global": None,
                "extracted_at": _utc_now_iso(),
            }
        )
        return doc_dna_id

    @staticmethod
    def get_document_dna(spine_data: dict[str, Any], doc_dna_id: str) -> dict[str, Any] | None:
        """Return the DNA record matching ``doc_dna_id``, or ``None`` if absent."""
        for record in spine_data.get("document_dna", []) or []:
            if isinstance(record, dict) and str(record.get("doc_dna_id")) == str(doc_dna_id):
                return record
        return None
