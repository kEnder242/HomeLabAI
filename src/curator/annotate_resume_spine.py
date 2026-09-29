#!/usr/bin/env python3
"""[FEAT-585 / FEAT-626 / WIS-487] Sprint 95.2 -- Multi-Version Resume AST Citation
& Diff Annotation.

Synthesizes the master lineage manifest for the resume paper:

    Portfolio_Dev/field_notes/data/papers/PAPER-RESUME_spine.json

Three self-contained sources are folded into one spine:

  1. ``PAPER-RESUME_v1.json``                            -- baseline (origin text).
  2. ``PAPER-RESUME_v2_farah_sharghi_recruiter_v1.json`` -- stylistic milestone
     (same bone identities, lens-attached ``review_flags``).
  3. ``resume_data.json``                                -- bullet cards keyed
     back into the AST by ``metadata.node_id``.

What the spine carries:

  * ``versions``      -- the lineage (``v1`` -> ``v2_recruiter``) with parent
    pointers, filenames and registration stamps.
  * ``topology``      -- every node's ``(section, block, role)`` coordinate per
    version, content-addressed by ``text_hash`` (never raw prose), plus the
    diff classification required by Story 95.2: ``MOVE`` / ``REWORD`` /
    ``ADD`` / ``DELETE`` (``UNCHANGED`` when a node is stable).
  * ``document_dna``  -- quarantined, document-scoped wisdom (FEAT-628):
    bullet cards from ``resume_data.json`` and rubric suggestions from the v2
    lens, each stamped ``DOC-RESUME-NNN`` with its origin node citation.
  * ``validation``    -- CP-1 token containment and CP-5 numeric literal
    preservation evidence, so "zero lost metrics" is a measured claim rather
    than an assertion.

Architectural mandates honoured here:
  * BKM-070 (Re-Anchoring Law) -- the spine is rebuilt from the certified ASTs
    on every run (never incrementally compounded), so replay is deterministic
    and idempotent.
  * BKM-015 -- regex is scoped strictly to deterministic ASCII token and numeric
    literal extraction for the CP-1/CP-5 evidence pass; it performs no semantic
    grading.
  * FEAT-628 / BKM-060 -- every ``document_dna`` record stays quarantined
    (``promoted_to_global=None``); promotion is an explicit, separately
    certified act.
  * Class 1 -- zero third-party dependencies, no network, no LLM call. Pure
    filesystem read plus the :class:`projection.bones.SpineManager` operators.

Run::

    python3 HomeLabAI/src/curator/annotate_resume_spine.py
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Resolve the projection package regardless of the invoking rootdir.
REPO_ROOT = Path(__file__).resolve().parents[3]
HOMELAB_SRC = REPO_ROOT / "HomeLabAI" / "src"
if str(HOMELAB_SRC) not in sys.path:
    sys.path.insert(0, str(HOMELAB_SRC))

from projection.bones import SpineManager

# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------

#: Spine ``paper_id``. ``SpineManager.spine_path`` prefixes ``PAPER-`` itself,
#: so this must be the *bare* id to land on ``PAPER-RESUME_spine.json`` and to
#: mint the ``DOC-RESUME-NNN`` stamps mandated by the sprint plan.
PAPER_ID = "RESUME"
SPINE_TITLE = "Jason Allred - Technical Resume & CV"

PAPERS_DIR = REPO_ROOT / "Portfolio_Dev" / "field_notes" / "data" / "papers"
RESUME_DATA = REPO_ROOT / "Portfolio_Dev" / "field_notes" / "data" / "resume_data.json"

#: ``(version_id, filename, parent_version, description)`` lineage declaration.
VERSION_SPECS: tuple[tuple[str, str, str | None, str], ...] = (
    (
        "v1",
        "PAPER-RESUME_v1.json",
        None,
        "Baseline Milestone (Origin Text + Raw Anchors)",
    ),
    (
        "v2_recruiter",
        "PAPER-RESUME_v2_farah_sharghi_recruiter_v1.json",
        "v1",
        "Stylistic Milestone (Farah Sharghi Recruiter Rubric)",
    ),
)

V1_ID, V2_ID = "v1", "v2_recruiter"

# Diff vocabulary for the topological cross-reference (Story 95.2 scope item 2).
OP_UNCHANGED, OP_MOVE, OP_REWORD, OP_ADD, OP_DELETE = (
    "UNCHANGED",
    "MOVE",
    "REWORD",
    "ADD",
    "DELETE",
)

# BKM-015: deterministic token / literal extraction only. No semantic judgement.
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NUMERIC_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Any:
    """Read ``path`` as UTF-8 JSON (FS-Researcher pattern -- no ambient state)."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# AST flattening
# ---------------------------------------------------------------------------


def _node_text(node: dict[str, Any]) -> str:
    """Canonical prose for a node, including the composed ``education`` shape.

    Education nodes carry no ``text`` key -- institution/degree/period are
    composed so they still receive a content address in the topology.
    """
    text = str(node.get("text", "") or "")
    if text.strip():
        return text
    composed = " ".join(
        str(node.get(key, "") or "").strip() for key in ("institution", "degree", "period")
    )
    return re.sub(r"\s+", " ", composed).strip()


def iter_document_nodes(document: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Flatten a Paper AST v1/v2 document into mappable topological records.

    Handles both carriers: section-level ``nodes[]`` and experience
    ``roles[].bullets[]``. A role's ``context_line`` is itself a coordinate
    (``block_id='context_line'``) so role prose participates in the diff.

    Yields dicts with ``node_id``, ``section_id``, ``block_id``, ``role``,
    ``text`` and the raw ``node`` (for citation/flag harvesting).
    """
    for section in document.get("sections", []) or []:
        section_id = str(section.get("section_id", section.get("id", "")))

        for node in section.get("nodes", []) or []:
            node_id = str(node.get("node_id", node.get("id", "")))
            if not node_id:
                continue
            yield {
                "node_id": node_id,
                "section_id": section_id,
                "block_id": str(node.get("type") or node.get("category") or "block"),
                "role": str(node.get("type") or node.get("category") or ""),
                "text": _node_text(node),
                "node": node,
            }

        for role in section.get("roles", []) or []:
            role_id = str(role.get("role_id", ""))
            context_line = str(role.get("context_line", "") or "")
            if role_id and context_line.strip():
                yield {
                    "node_id": role_id,
                    "section_id": section_id,
                    "block_id": "context_line",
                    "role": role_id,
                    "text": context_line,
                    "node": role,
                }

            for index, bullet in enumerate(role.get("bullets", []) or [], start=1):
                node_id = str(bullet.get("node_id", bullet.get("id", "")))
                if not node_id:
                    continue
                yield {
                    "node_id": node_id,
                    "section_id": section_id,
                    "block_id": f"bullet_{index:02d}",
                    "role": role_id,
                    "text": _node_text(bullet),
                    "node": bullet,
                }


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(text).lower()))


def _numeric_literals(text: str) -> set[str]:
    return set(_NUMERIC_RE.findall(str(text)))


# ---------------------------------------------------------------------------
# Spine construction
# ---------------------------------------------------------------------------


def build_topology(spine: dict[str, Any], version_id: str, document: dict[str, Any]) -> int:
    """Map every node of ``document`` into ``spine['topology']`` for ``version_id``.

    Returns the number of coordinates mapped. Text is content-addressed inside
    :meth:`SpineManager.map_node`; the version file stays the single owner of
    the prose.
    """
    mapped = 0
    for record in iter_document_nodes(document):
        SpineManager.map_node(
            spine,
            record["node_id"],
            version_id,
            record["section_id"],
            block_id=record["block_id"],
            role=record["role"],
            text=record["text"],
        )
        mapped += 1
    return mapped


def classify_operations(spine: dict[str, Any]) -> dict[str, int]:
    """Stamp a diff operation onto every topology coordinate and count them.

    ``text_hash`` equality is the identity test (BKM-070: bones are immutable
    content anchors, so identical prose is an unchanged anchor even when a new
    lens hangs flags off it).
    """
    counts: dict[str, int] = {
        OP_UNCHANGED: 0,
        OP_MOVE: 0,
        OP_REWORD: 0,
        OP_ADD: 0,
        OP_DELETE: 0,
    }

    for node_id, node in (spine.get("topology", {}) or {}).items():
        versions = node.get("versions", {}) or {}
        baseline = versions.get(V1_ID)
        revised = versions.get(V2_ID)

        if baseline is None:
            operation = OP_ADD
        elif revised is None:
            operation = OP_DELETE
        elif baseline.get("text_hash") != revised.get("text_hash"):
            operation = OP_REWORD
        elif (baseline.get("section_id"), baseline.get("block_id"), baseline.get("role")) != (
            revised.get("section_id"),
            revised.get("block_id"),
            revised.get("role"),
        ):
            operation = OP_MOVE
        else:
            operation = OP_UNCHANGED

        counts[operation] += 1
        # Annotate the newest coordinate (the reading surface for the studio);
        # the baseline coordinate keeps the operation too so either side reads.
        for coordinate in (baseline, revised):
            if isinstance(coordinate, dict):
                coordinate["operation"] = operation
        node["node_id"] = node.get("node_id", str(node_id))

    return counts


def verify_containment(
    baseline: dict[str, Any], revised: dict[str, Any]
) -> dict[str, Any]:
    """CP-1 token containment + CP-5 numeric literal preservation evidence.

    Every baseline node must appear in the revision with the same token set
    (CP-1) and must not lose a single numeric literal (CP-5). Any breach is
    reported verbatim so the orchestrator can treat it as a hard failure rather
    than a metric regression.
    """
    base_nodes = {r["node_id"]: r for r in iter_document_nodes(baseline)}
    rev_nodes = {r["node_id"]: r for r in iter_document_nodes(revised)}

    containment_violations: list[dict[str, Any]] = []
    literal_violations: list[dict[str, Any]] = []
    missing_nodes: list[str] = []
    tokens_checked = 0
    literals_checked = 0

    for node_id, record in sorted(base_nodes.items()):
        counterpart = rev_nodes.get(node_id)
        if counterpart is None:
            missing_nodes.append(node_id)
            continue

        base_tokens = _tokens(record["text"])
        rev_tokens = _tokens(counterpart["text"])
        tokens_checked += len(base_tokens)
        lost_tokens = sorted(base_tokens - rev_tokens)
        if lost_tokens:
            containment_violations.append(
                {"node_id": node_id, "lost_tokens": lost_tokens[:20]}
            )

        base_literals = _numeric_literals(record["text"])
        literals_checked += len(base_literals)
        rev_literals = _numeric_literals(counterpart["text"])
        lost_literals = sorted(base_literals - rev_literals)
        if lost_literals:
            literal_violations.append(
                {"node_id": node_id, "lost_literals": lost_literals[:20]}
            )

    return {
        "cp1_token_containment": {
            "nodes_checked": len(base_nodes),
            "tokens_checked": tokens_checked,
            "missing_nodes": missing_nodes,
            "violations": containment_violations,
            "passed": not containment_violations and not missing_nodes,
        },
        "cp5_numeric_literals": {
            "nodes_checked": len(base_nodes),
            "literals_checked": literals_checked,
            "violations": literal_violations,
            "passed": not literal_violations,
        },
    }


# ---------------------------------------------------------------------------
# Document DNA vault
# ---------------------------------------------------------------------------


def _annotate_dna(spine: dict[str, Any], doc_dna_id: str, extra: dict[str, Any]) -> None:
    """Attach citation metadata to an already-allocated DNA record."""
    record = SpineManager.get_document_dna(spine, doc_dna_id)
    if record is None:  # pragma: no cover - defensive; allocation just succeeded
        return
    for key, value in extra.items():
        record.setdefault(key, value)


def _section_default_nodes(document: dict[str, Any]) -> dict[str, str]:
    """``section_id -> first node_id``, used to anchor cards without a node_id."""
    defaults: dict[str, str] = {}
    for record in iter_document_nodes(document):
        defaults.setdefault(record["section_id"], record["node_id"])
    return defaults


def ingest_bullet_cards(spine: dict[str, Any], cards: Any, anchor_doc: dict[str, Any]) -> int:
    """Ingest ``resume_data.json`` bullet cards as document-scoped DNA.

    Each card cites its origin node through ``metadata.node_id``, falling back to
    the first node of ``metadata.section`` when the card is a career-core
    summary rather than a bullet.
    """
    if not isinstance(cards, list):
        return 0
    defaults = _section_default_nodes(anchor_doc)

    ingested = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        metadata = card.get("metadata", {}) or {}
        origin = str(
            metadata.get("node_id")
            or defaults.get(str(metadata.get("section", "")), "")
        )
        theme = " ".join(str(tag) for tag in card.get("tags", []) or []) or str(
            card.get("domain", "")
        )
        text = str(card.get("content") or card.get("summary") or "")
        if not text.strip():
            continue

        doc_dna_id = SpineManager.add_document_dna(
            spine,
            theme,
            str(card.get("title", "")),
            text,
            origin,
        )
        _annotate_dna(
            spine,
            doc_dna_id,
            {
                "source": "resume_data",
                "card_id": str(card.get("id", "")),
                "citations": [str(link) for link in card.get("explicit_links", []) or []],
            },
        )
        ingested += 1

    return ingested


def ingest_review_suggestions(spine: dict[str, Any], document: dict[str, Any]) -> int:
    """Ingest every v2 lens ``review_flag`` suggestion as document-scoped DNA."""
    ingested = 0
    for record in iter_document_nodes(document):
        for flag in record["node"].get("review_flags", []) or []:
            if not isinstance(flag, dict):
                continue
            suggestion = str(flag.get("suggestion", "") or "")
            if not suggestion.strip():
                continue
            severity = str(flag.get("severity", "") or "")
            category = str(flag.get("category", "") or "")
            rule_id = str(flag.get("rule_id", "") or flag.get("id", "") or "")

            doc_dna_id = SpineManager.add_document_dna(
                spine,
                rule_id or category,
                f"{record['node_id']} - {category or 'RUBRIC'}"
                + (f" ({severity})" if severity else ""),
                suggestion,
                record["node_id"],
            )
            _annotate_dna(
                spine,
                doc_dna_id,
                {
                    "source": "v2_lens_flag",
                    "version_id": V2_ID,
                    "rule_id": rule_id,
                    "flag_id": str(flag.get("id", "")),
                    "category": category,
                    "severity": severity,
                    "status": str(flag.get("status", "")),
                    "citations": [
                        str(c) for c in record["node"].get("citations", []) or []
                    ],
                },
            )
            ingested += 1

    return ingested


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def synthesize() -> Path:
    """Build the resume spine from source and persist it. Returns the path."""
    documents: dict[str, dict[str, Any]] = {}
    for version_id, filename, _parent, _description in VERSION_SPECS:
        documents[version_id] = load_json(PAPERS_DIR / filename)
    cards = load_json(RESUME_DATA)

    spine = SpineManager.empty_spine(PAPER_ID)
    # `empty_spine` takes no title kwarg; the title is asserted post-construction.
    spine["title"] = SPINE_TITLE

    for version_id, filename, parent_version, description in VERSION_SPECS:
        SpineManager.register_version(
            spine, version_id, filename, parent_version, description
        )

    for version_id in (V1_ID, V2_ID):
        build_topology(spine, version_id, documents[version_id])

    operation_counts = classify_operations(spine)

    cards_ingested = ingest_bullet_cards(spine, cards, documents[V1_ID])
    flags_ingested = ingest_review_suggestions(spine, documents[V2_ID])

    validation = verify_containment(documents[V1_ID], documents[V2_ID])
    validation["operation_counts"] = operation_counts
    validation["topology_nodes"] = len(spine["topology"])
    validation["document_dna_records"] = len(spine["document_dna"])
    validation["source_cards"] = cards_ingested
    validation["source_review_flags"] = flags_ingested
    validation["zero_lost_metrics"] = bool(
        validation["cp1_token_containment"]["passed"]
        and validation["cp5_numeric_literals"]["passed"]
    )
    spine["validation"] = validation

    return SpineManager.save_spine(PAPER_ID, spine, base_dir=PAPERS_DIR)


def main() -> int:
    path = synthesize()
    spine = SpineManager.load_spine(PAPER_ID, base_dir=PAPERS_DIR)
    validation = spine.get("validation", {})

    print(f"[SPR-95.2] Spine written: {path}")
    print(
        "  versions: "
        + ", ".join(
            f"{v['version_id']}<-{v['parent_version'] or 'root'}"
            for v in spine.get("versions", [])
        )
    )
    print(f"  topology nodes: {len(spine.get('topology', {}))}")
    print(
        "  operations: "
        + ", ".join(
            f"{op}={count}"
            for op, count in (validation.get("operation_counts") or {}).items()
            if count
        )
    )
    print(
        f"  document_dna: {len(spine.get('document_dna', []))} "
        f"(cards={validation.get('source_cards')}, "
        f"flags={validation.get('source_review_flags')})"
    )
    print(
        "  CP-1 token containment: "
        f"{'PASS' if validation.get('cp1_token_containment', {}).get('passed') else 'FAIL'}"
    )
    print(
        "  CP-5 numeric literals: "
        f"{'PASS' if validation.get('cp5_numeric_literals', {}).get('passed') else 'FAIL'}"
    )

    return 0 if validation.get("zero_lost_metrics") else 1


if __name__ == "__main__":
    raise SystemExit(main())
