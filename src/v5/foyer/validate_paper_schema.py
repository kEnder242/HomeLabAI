#!/usr/bin/env python3
"""
[SPR-82.1] Two-Tier AST Schema Strict Validator (HomeLabAI/src/v5/foyer/validate_paper_schema.py)
=================================================================================================
Strictly validates the canonical two-tier document AST emitted by
`Portfolio_Dev/scripts/parse_document_to_ast.py`:

    Root      : { id?, title, bone_collection[], _candidate_pool[], sections[] }
    Section   : { id, heading, bone_collection[], _candidate_pool[], paragraphs[] }
    Paragraph : { id, text, bullet_type?, citations[], bone_collection[], _candidate_pool[] }

Invariants (SPR-82.0 architectural guardrail 3 - AST Strictness):
  1. TWO-TIER INVARIANT: both `bone_collection[]` (active bones, promoted during
     Phase 2 curation) and `_candidate_pool[]` (discovered candidates, Phase 1)
     are REQUIRED at Root, Section, and Paragraph levels of every imported document.
  2. Tier arrays must be lists; `bone_collection` and `citations` entries must match
     the registered citation syntax (FEAT-xxx, BKM-xxx, WIS-xxx, PHL-xxx, DISC-xxx,
     LAB-xxx, GEM-xxx, PROTO-xxx, ARXIV:nnnn.nnnnn, doi:...).
  3. ids are required and globally unique at their level; title/heading/text must be
     non-empty strings; `bullet_type` (when present) must be 'bullet' or 'paragraph'.
  4. Unknown keys are ignored for forward compatibility (metadata such as `level`,
     `subtitle`, `author`, `date`, `status`, `updated_at`).

API mirrors the legacy Portfolio_Dev/scripts/validate_paper_schema.py so call sites
share the familiar `validate_paper_dict(data, source_name) -> (bool, list[str])` contract.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

CITATION_PATTERN = re.compile(
    r"^(?:PHL|DISC|FEAT|BKM|PROTO|ARXIV|GEM|WIS|LAB)-[A-Za-z0-9_.\-]+$"
    r"|^ARXIV:\d+\.\d+$|^arXiv:\d+\.\d+$"
    r"|^doi:[A-Za-z0-9_.\-/]+$",
    re.IGNORECASE,
)

VALID_BULLET_TYPES = ("bullet", "paragraph")

__all__ = ["CITATION_PATTERN", "validate_paper_dict", "validate_paper_path", "main"]


def _validate_pool(node: Dict[str, Any], prefix: str, errors: List[str]) -> None:
    """Validate the two-tier palette keys (bone_collection[] + _candidate_pool[]) on a node."""
    bone = node.get("bone_collection")
    if bone is None:
        errors.append(f"{prefix}: missing required 'bone_collection' (two-tier invariant).")
    elif not isinstance(bone, list):
        errors.append(f"{prefix}: 'bone_collection' must be a list.")
    else:
        for entry in bone:
            if not isinstance(entry, str) or not CITATION_PATTERN.match(entry):
                errors.append(f"{prefix}: 'bone_collection' entry '{entry}' is not a valid citation ID.")

    pool = node.get("_candidate_pool")
    if pool is None:
        errors.append(f"{prefix}: missing required '_candidate_pool' (two-tier invariant).")
    elif not isinstance(pool, list):
        errors.append(f"{prefix}: '_candidate_pool' must be a list.")
    else:
        for entry in pool:
            if not isinstance(entry, str) or not entry.strip():
                errors.append(f"{prefix}: '_candidate_pool' entry '{entry!r}' must be a non-empty string.")


def _validate_citations(node: Dict[str, Any], prefix: str, errors: List[str]) -> None:
    """Validate the paragraph-level explicit `citations[]` list."""
    citations = node.get("citations")
    if citations is None:
        errors.append(f"{prefix}: missing required 'citations'.")
    elif not isinstance(citations, list):
        errors.append(f"{prefix}: 'citations' must be a list.")
    else:
        for entry in citations:
            if not isinstance(entry, str) or not CITATION_PATTERN.match(entry):
                errors.append(f"{prefix}: 'citations' entry '{entry}' is not a valid citation ID.")


def validate_paper_dict(data: Any, source_name: str = "paper") -> Tuple[bool, List[str]]:
    """Strictly validate an in-memory two-tier AST document against the schema invariants.

    Returns `(passed, errors)` where `errors` is a human-readable list of every
    invariant violation found (empty when `passed` is True).
    """
    errors: List[str] = []
    prefix = source_name or "paper"

    if not isinstance(data, dict):
        return False, [f"{prefix}: top-level document must be a JSON object."]

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append(f"{prefix}: missing or empty top-level 'title'.")

    _validate_pool(data, prefix, errors)

    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        errors.append(f"{prefix}: 'sections' must be a non-empty list.")
        return (len(errors) == 0), errors

    sec_ids: set = set()
    par_ids: set = set()
    for sec_idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            errors.append(f"{prefix}: section index {sec_idx} must be an object.")
            continue
        sec_id = sec.get("id")
        if not isinstance(sec_id, str) or not sec_id.strip():
            errors.append(f"{prefix}: section index {sec_idx} missing non-empty 'id'.")
            sec_label = f"Section (index {sec_idx})"
        elif sec_id in sec_ids:
            errors.append(f"{prefix}: duplicate section id '{sec_id}'.")
            sec_label = f"Section '{sec_id}'"
        else:
            sec_ids.add(sec_id)
            sec_label = f"Section '{sec_id}'"

        heading = sec.get("heading")
        if not isinstance(heading, str) or not heading.strip():
            errors.append(f"{prefix}: {sec_label} missing non-empty 'heading'.")

        _validate_pool(sec, f"{prefix}: {sec_label}", errors)

        paragraphs = sec.get("paragraphs")
        if not isinstance(paragraphs, list):
            errors.append(f"{prefix}: {sec_label} 'paragraphs' must be a list.")
            continue
        for par_idx, par in enumerate(paragraphs):
            if not isinstance(par, dict):
                errors.append(f"{prefix}: {sec_label} paragraph index {par_idx} must be an object.")
                continue
            par_id = par.get("id")
            if not isinstance(par_id, str) or not par_id.strip():
                errors.append(f"{prefix}: {sec_label} paragraph index {par_idx} missing non-empty 'id'.")
                par_label = f"Paragraph (index {par_idx})"
            elif par_id in par_ids:
                errors.append(f"{prefix}: duplicate paragraph id '{par_id}'.")
                par_label = f"Paragraph '{par_id}'"
            else:
                par_ids.add(par_id)
                par_label = f"Paragraph '{par_id}'"

            text = par.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{prefix}: {par_label} missing non-empty 'text'.")

            bullet_type = par.get("bullet_type")
            if bullet_type is not None and bullet_type not in VALID_BULLET_TYPES:
                errors.append(
                    f"{prefix}: {par_label} invalid bullet_type '{bullet_type}' "
                    f"(must be 'bullet' or 'paragraph')."
                )

            _validate_citations(par, f"{prefix}: {par_label}", errors)
            _validate_pool(par, f"{prefix}: {par_label}", errors)

    return (len(errors) == 0), errors


def validate_paper_path(paper_path: str) -> bool:
    """Validate a JSON file on disk against the two-tier AST schema."""
    path = Path(paper_path)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"❌ JSON parse error for {path.name}: {exc}")
        return False

    passed, errors = validate_paper_dict(data, source_name=path.name)
    if not passed:
        print(f"❌ Two-tier AST validation FAILED for {path.name} with {len(errors)} error(s):")
        for err in errors:
            print(f"   - {err}")
        return False

    sections = data.get("sections", [])
    par_count = sum(len(s.get("paragraphs", [])) for s in sections)
    print(f"✅ Two-tier AST validation PASSED for {path.name} ({len(sections)} sections, {par_count} paragraphs).")
    return True


def main() -> None:
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_file():
            sys.exit(0 if validate_paper_path(str(target)) else 1)
    print("Usage: python3 validate_paper_schema.py <paper.json>")
    sys.exit(2)


if __name__ == "__main__":
    main()
