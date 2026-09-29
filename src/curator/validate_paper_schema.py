#!/usr/bin/env python3
"""
[Story 94.3 / SPR-94.0] Paper AST Schema v2 & Rubric v2 Deterministic Gate

Schema gate for the Curatorial projection substrate. Enforces the structural
invariants CP-1, CP-5 and CP-7 over Paper AST JSON payloads and over the
``lens.v2`` rubric envelope emitted by ``projection.lenses.craft_lens``.

BKM-015 taxonomy: every check in this module is deterministic AST / JSON schema
traversal. Regex is scoped strictly to ASCII token extraction -- code-fence and
inline-code delimiters, and numeric literal shape. No semantic or natural
language judgement happens here; that is the LLM-judge tier's responsibility.

Invariants
----------
CP-1  Code token containment. A code token (fenced block or inline span) must
      open and close inside a single text leaf. A delimiter straddling two
      leaves is a containment violation, not a formatting preference.
CP-5  Numeric literal integrity. Quantitative anchors must be well formed. Float
      placeholders (``nan`` / ``inf``) and magnitude-less quantifiers ("reduced
      latency by %") corrupt downstream numeric-equivalence judgement, e.g. the
      ``$10M == 10 million`` assertion class.
CP-7  Section isolation and re-projection idempotence. Identifiers occupy a single
      document-wide namespace, so two sections can never claim the same node, and
      validation is a pure function of the payload: re-validating an unchanged
      document yields an identical verdict.

Two AST dialects share the paper corpus and both are accepted:
  * resume dialect  -- ``paper_id`` / ``section_id`` / ``nodes`` / ``roles``
  * academic dialect -- ``id`` / ``paragraphs`` / ``bone_collections``

The rubric constants below mirror ``HomeLabAI/src/projection/lenses.py`` (Story
94.2). They are duplicated deliberately rather than imported: this gate must stay
hermetic and runnable without the projection engine. Keep the two in sync.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "CATEGORIES",
    "CP1_CODE_TOKEN_CONTAINMENT",
    "CP5_NUMERIC_LITERAL_INTEGRITY",
    "CP7_SECTION_ISOLATION",
    "DETECTOR_BUDGET_KEYS",
    "LENS_SCHEMA_VERSION",
    "RULE_FIELDS",
    "SEVERITIES",
    "TIERS",
    "is_lens_payload",
    "is_paper_ast_payload",
    "main",
    "validate_file",
    "validate_lens_schema_v2",
    "validate_paper_ast",
]

# --- Invariant tags (FEAT-622) -------------------------------------------------
CP1_CODE_TOKEN_CONTAINMENT = "CP-1"
CP5_NUMERIC_LITERAL_INTEGRITY = "CP-5"
CP7_SECTION_ISOLATION = "CP-7"

# --- Rubric v2 contract (mirrors projection.lenses) ---------------------------
LENS_SCHEMA_VERSION = "lens.v2"
TIERS: tuple[str, ...] = ("tier_0_structural", "tier_1_semantic")
SEVERITIES: frozenset[str] = frozenset(
    {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
)
CATEGORIES: frozenset[str] = frozenset({"PROSE", "REFINEMENT", "CONNECTION", "STRUCTURE"})
RULE_FIELDS: tuple[str, ...] = (
    "rule_id",
    "category",
    "severity",
    "description",
    "tier",
)
DETECTOR_BUDGET_KEYS: tuple[str, ...] = (
    "tier_0",
    "tier_1",
    "max_flags_per_node",
    "max_total_flags",
)

# Semantic-only rule ids. CP-1 bars these from tier_0_structural, which must be
# decidable by deterministic traversal alone (BKM-015).
SEMANTIC_ONLY_RULES: frozenset[str] = frozenset(
    {
        "FIRST_3_WORDS_POWER_VERB",
        "SO_WHAT_METRIC_DRILL",
        "THREE_SENTENCE_SUMMARY_HOOK",
    }
)

# --- AST dialect vocabulary ----------------------------------------------------
# Identifier-bearing keys, across both dialects. A single document-wide namespace
# is what CP-7 section isolation means: no two sections may claim one node.
_ID_KEYS: frozenset[str] = frozenset(
    {"id", "node_id", "section_id", "role_id", "paragraph_id"}
)
# Keys whose string value is prose/code content subject to CP-1 containment.
_CONTENT_KEYS: frozenset[str] = frozenset(
    {"text", "cached_words", "heading", "title", "context_line", "description"}
)
# Prose body keys additionally subject to CP-5 numeric integrity.
_PROSE_BODY_KEYS: frozenset[str] = frozenset({"text", "cached_words"})

# CP-1: fenced block delimiter. An odd count means the fence straddles leaves.
_FENCE_RE = re.compile(r"```")
# CP-1: any inline-code delimiter, counted after fences are removed.
_INLINE_BACKTICK = "`"
# CP-5: float placeholders produced by a broken numeric substitution.
_FLOAT_PLACEHOLDER_RE = re.compile(r"\b(?:nan|inf|infinity)\b", re.IGNORECASE)
# CP-5: a percent sign carrying no magnitude ("reduced latency by %").
#
# Currency is deliberately NOT checked here. A bare '$' is indistinguishable
# from a LaTeX math delimiter by local shape alone -- the corpus legitimately
# contains inline math such as ($\vec{v}_{\text{style}}$) -- so judging it
# deterministically would be a guess. Per BKM-015 that ambiguity belongs to the
# LLM-judge tier, not to this structural gate. '%' is unambiguous: LaTeX escapes
# it as '\%', so a percent with no adjacent digit is a genuinely broken anchor.
_MAGNITUDELESS_RE = re.compile(r"(?<!\w)%(?![%0-9])")


def _walk_strings(node: Any, keys: frozenset[str], path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield ``(json_path, value)`` for every string under an allow-listed key."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            if key in keys and isinstance(value, str):
                yield child_path, value
            else:
                yield from _walk_strings(value, keys, child_path)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _walk_strings(value, keys, f"{path}[{index}]")


def _collect_ids(node: Any) -> Iterator[tuple[str, str]]:
    """Yield ``(json_path, identifier)`` for every identifier-bearing field."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key in _ID_KEYS and isinstance(value, str) and value.strip():
                yield key, value
            else:
                yield from _collect_ids(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _collect_ids(value)


def _check_code_token_containment(ast_data: Mapping[str, Any], errors: list[str]) -> None:
    """CP-1: every code token must be balanced inside a single text leaf."""
    for path, text in _walk_strings(ast_data, _CONTENT_KEYS):
        # A complete fenced block contributes an even number of fence delimiters.
        # An odd count means the fence opened here and closed in another leaf.
        if len(_FENCE_RE.findall(text)) % 2 != 0:
            errors.append(
                f"[{CP1_CODE_TOKEN_CONTAINMENT}] {path}: unclosed code fence; "
                "a code token must open and close inside the same text leaf."
            )
            continue
        # Count inline delimiters with balanced fences removed, so backticks
        # living inside a fenced block are not mistaken for inline spans.
        without_fences = _FENCE_RE.sub("", text)
        if without_fences.count(_INLINE_BACKTICK) % 2 != 0:
            errors.append(
                f"[{CP1_CODE_TOKEN_CONTAINMENT}] {path}: unpaired inline-code delimiter; "
                "a code token must open and close inside the same text leaf."
            )


def _check_numeric_literal_integrity(
    ast_data: Mapping[str, Any], errors: list[str]
) -> None:
    """CP-5: quantitative anchors must be well formed for equivalence judging."""
    for path, text in _walk_strings(ast_data, _PROSE_BODY_KEYS):
        placeholder = _FLOAT_PLACEHOLDER_RE.search(text)
        if placeholder is not None:
            errors.append(
                f"[{CP5_NUMERIC_LITERAL_INTEGRITY}] {path}: float placeholder "
                f"'{placeholder.group(0)}' in prose; quantitative anchors must be "
                "concrete literals."
            )
        quantifier = _MAGNITUDELESS_RE.search(text)
        if quantifier is not None:
            errors.append(
                f"[{CP5_NUMERIC_LITERAL_INTEGRITY}] {path}: percent sign carries no "
                "magnitude; attach a numeric literal to the quantified anchor."
            )


def _check_section_isolation(ast_data: Mapping[str, Any], errors: list[str]) -> bool:
    """CP-7: sections are well formed and identifiers are document-wide unique.

    Returns True when traversal may continue into the leaf-level checks.
    """
    sections = ast_data.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append(
            f"[{CP7_SECTION_ISOLATION}] $.sections: must be a non-empty list of "
            "section objects."
        )
        return False

    for index, section in enumerate(sections):
        if not isinstance(section, Mapping):
            errors.append(
                f"[{CP7_SECTION_ISOLATION}] $.sections[{index}]: section must be an "
                "object."
            )
            return False
        has_heading = isinstance(section.get("heading"), str) and section["heading"].strip()
        section_id = section.get("section_id") or section.get("id")
        if not has_heading:
            errors.append(
                f"[{CP7_SECTION_ISOLATION}] $.sections[{index}]: missing non-empty "
                "'heading'."
            )
        if not (isinstance(section_id, str) and section_id.strip()):
            errors.append(
                f"[{CP7_SECTION_ISOLATION}] $.sections[{index}]: missing non-empty "
                "section identifier ('section_id' or 'id')."
            )

    # Document-wide identifier namespace. Duplicates mean a section is claiming a
    # node another section already owns, or a re-projection emitted a twin.
    seen: dict[str, str] = {}
    for key, identifier in _collect_ids(ast_data):
        if identifier in seen:
            errors.append(
                f"[{CP7_SECTION_ISOLATION}] identifier '{identifier}' is not isolated: "
                f"already declared as '{seen[identifier]}', redeclared as '{key}'. "
                "Identifiers must be unique across the whole document."
            )
        else:
            seen[identifier] = key
    return True


def validate_paper_ast(ast_data: dict) -> tuple[bool, list[str]]:
    """Validate a Paper AST payload against the structural gate.

    Enforces required top-level keys, either nested or inline metadata
    presentation, and the CP-1 / CP-5 / CP-7 structural invariants. Both the
    resume dialect (``paper_id``) and the academic dialect (``id``) are accepted.

    Never raises: a non-dict payload returns ``(False, [error])``. The input is
    not mutated, so the verdict is a pure function of the payload (CP-7
    re-projection idempotence).
    """
    if not isinstance(ast_data, dict):
        return False, [f"[{CP7_SECTION_ISOLATION}] $: payload must be a JSON object."]

    errors: list[str] = []

    # Required keys. Identity is satisfied by either dialect's identifier field.
    if not ("paper_id" in ast_data or "id" in ast_data):
        errors.append(
            "$.<root>: missing required paper identifier ('paper_id' or 'id')."
        )
    if "title" not in ast_data:
        errors.append("$.<root>: missing required field 'title'.")
    elif not (isinstance(ast_data["title"], str) and ast_data["title"].strip()):
        errors.append("$.title: must be a non-empty string.")
    if "sections" not in ast_data:
        errors.append("$.<root>: missing required field 'sections'.")

    # Metadata: nested under 'metadata', or presented inline on the root.
    has_nested_metadata = "metadata" in ast_data
    has_inline_metadata = any(
        key in ast_data for key in ("author", "contact", "revision_id")
    )
    if not (has_nested_metadata or has_inline_metadata):
        errors.append(
            "$.<root>: missing metadata. Provide nested 'metadata', or inline "
            "'author', 'contact' or 'revision_id'."
        )
    if has_nested_metadata and not isinstance(ast_data["metadata"], Mapping):
        errors.append("$.metadata: must be an object when present.")

    if "sections" not in ast_data:
        return False, errors

    if _check_section_isolation(ast_data, errors):
        _check_code_token_containment(ast_data, errors)
        _check_numeric_literal_integrity(ast_data, errors)

    return len(errors) == 0, errors


def is_lens_payload(payload: Mapping[str, Any]) -> bool:
    """True when the payload looks like a rubric v2 envelope rather than a Paper AST."""
    if not isinstance(payload, Mapping):
        return False
    if "schema" in payload or "schema_version" in payload:
        return True
    return "detector_budget" in payload or "rubric" in payload


def is_paper_ast_payload(payload: Mapping[str, Any]) -> bool:
    """True when the payload carries the Paper AST structural signature.

    The corpus also holds documents that are deliberately not Paper ASTs, such as
    ``style_resume_v1.json`` (a layout/typography profile referenced by
    ``style_schema_ref``). Those are reported as skipped rather than failed, so
    the gate never passes or condemns a document class it was not written to
    judge.

    Identity alone is enough to attempt validation. A payload that declares a
    paper id but has lost its ``sections`` is a *corrupt* AST and must be
    reported as such, not skipped -- skipping it would let a truncated document
    pass the gate silently.
    """
    if not isinstance(payload, Mapping):
        return False
    return "paper_id" in payload or "id" in payload


def _unwrap_lens(lens_data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Accept either a craft_lens envelope or a bare rubric object."""
    rubric = lens_data.get("rubric")
    if isinstance(rubric, Mapping):
        return rubric
    return lens_data


def validate_lens_schema_v2(lens_data: dict) -> tuple[bool, list[str]]:
    """Validate a lens / rubric v2 payload.

    Checks the ``lens.v2`` schema tag, the tier partition, per-rule field
    integrity, and the detector budget caps. The version tag is accepted under
    either ``schema_version`` or ``schema`` so this gate agrees with the payloads
    produced by ``projection.lenses.craft_lens``.

    Never raises: a non-dict payload returns ``(False, [error])``.
    """
    if not isinstance(lens_data, dict):
        return False, ["$: lens payload must be a JSON object."]

    if lens_data.get("status") == "UNSAFE_TO_CRAFT":
        return False, ["$: lens was refused at compile time (UNSAFE_TO_CRAFT)."]

    rubric = _unwrap_lens(lens_data)
    if not isinstance(rubric, Mapping):
        return False, ["$.rubric: must be an object when present."]

    errors: list[str] = []

    # Schema tag. Both spellings are in circulation across the codebase.
    version = rubric.get("schema_version", rubric.get("schema"))
    if version is None:
        errors.append(
            "$.<root>: missing schema tag. Provide 'schema_version' (or 'schema') "
            f"= '{LENS_SCHEMA_VERSION}'."
        )
    elif version != LENS_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version: expected '{LENS_SCHEMA_VERSION}', found '{version}'."
        )

    lens_id = rubric.get("lens_id")
    if not (isinstance(lens_id, str) and lens_id.strip()):
        errors.append("$.lens_id: must be a non-empty string.")
    title = rubric.get("title")
    if not (isinstance(title, str) and title.strip()):
        errors.append("$.title: must be a non-empty string.")
    if not isinstance(rubric.get("persona"), Mapping):
        errors.append("$.persona: must be an object.")

    rules = rubric.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("$.rules: must be a non-empty list of rule objects.")
        rules = []
    else:
        seen: set[str] = set()
        for index, rule in enumerate(rules):
            path = f"$.rules[{index}]"
            if not isinstance(rule, Mapping):
                errors.append(f"{path}: rule must be an object.")
                continue
            for field in RULE_FIELDS:
                if field not in rule:
                    errors.append(f"{path}: missing required rule field '{field}'.")
            rule_id = rule.get("rule_id")
            if not (isinstance(rule_id, str) and rule_id.strip()):
                errors.append(f"{path}.rule_id: must be a non-empty string.")
            elif rule_id in seen:
                errors.append(f"{path}.rule_id: duplicate rule id '{rule_id}'.")
            else:
                seen.add(rule_id)
            if rule.get("severity") not in SEVERITIES:
                errors.append(
                    f"{path}.severity: '{rule.get('severity')}' is not one of "
                    f"{sorted(SEVERITIES)}."
                )
            if rule.get("category") not in CATEGORIES:
                errors.append(
                    f"{path}.category: '{rule.get('category')}' is not one of "
                    f"{sorted(CATEGORIES)}."
                )
            if rule.get("tier") not in TIERS:
                errors.append(
                    f"{path}.tier: '{rule.get('tier')}' is not one of {list(TIERS)}."
                )
            # CP-1: tier_0 must stay decidable by deterministic traversal.
            if (
                rule.get("tier") == "tier_0_structural"
                and rule.get("rule_id") in SEMANTIC_ONLY_RULES
            ):
                errors.append(
                    f"{path}: [{CP1_CODE_TOKEN_CONTAINMENT}] semantic rule "
                    f"'{rule.get('rule_id')}' may not sit in 'tier_0_structural'; "
                    "tier_0 is decidable by deterministic traversal only (BKM-015)."
                )

    # Tier manifest, when declared, must cover exactly the tier partition.
    manifest = rubric.get("tiers", rubric.get("tier_manifest"))
    if manifest is not None:
        if not isinstance(manifest, Mapping):
            errors.append("$.tiers: tier manifest must be an object when present.")
        elif set(manifest.keys()) != set(TIERS):
            errors.append(
                f"$.tiers: must declare exactly {list(TIERS)}, found "
                f"{sorted(manifest.keys())}."
            )

    budget = rubric.get("detector_budget")
    if budget is None:
        errors.append("$.detector_budget: missing required detector budget.")
    elif not isinstance(budget, Mapping):
        errors.append("$.detector_budget: must be an object.")
    else:
        for key in DETECTOR_BUDGET_KEYS:
            value = budget.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(
                    f"$.detector_budget.{key}: must be a positive integer, found "
                    f"{value!r}."
                )
        if not errors:
            tier_counts = {
                tier: sum(1 for rule in rules if rule.get("tier") == tier)
                for tier in TIERS
            }
            for tier, count in tier_counts.items():
                cap = budget.get(tier)
                if isinstance(cap, int) and count > cap:
                    errors.append(
                        f"$.detector_budget.{tier}: {count} rules exceed the budget "
                        f"cap of {cap}."
                    )

    return len(errors) == 0, errors


def validate_file(path: Path) -> tuple[bool, list[str]]:
    """Validate a JSON file on disk, auto-detecting AST vs rubric v2 payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, [f"{path}: file not found."]
    except json.JSONDecodeError as exc:
        return False, [f"{path}: invalid JSON ({exc})."]
    if not isinstance(payload, dict):
        return False, [f"{path}: root must be a JSON object."]
    if is_lens_payload(payload):
        return validate_lens_schema_v2(payload)
    return validate_paper_ast(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 when every target validates, 1 otherwise."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print(
            "Usage: validate_paper_schema.py <file.json> [file.json ...]\n"
            "       Validates Paper AST and lens.v2 rubric payloads.\n"
            "       Exit 0 = all valid, 1 = at least one invalid."
        )
        return 0 if not args else 1

    all_passed = True
    for raw in args:
        path = Path(raw).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            all_passed = False
            print(f"[FAIL] {path}: file not found.")
            continue
        except json.JSONDecodeError as exc:
            all_passed = False
            print(f"[FAIL] {path}: invalid JSON ({exc}).")
            continue

        if is_lens_payload(payload):
            passed, errors = validate_lens_schema_v2(payload)
            kind = "lens.v2"
        elif is_paper_ast_payload(payload):
            passed, errors = validate_paper_ast(payload)
            kind = "paper-ast"
        else:
            # A recognised non-AST document (e.g. a style profile). Out of scope
            # for this gate, so it neither passes nor fails the run.
            print(f"[SKIP] {path}: not a Paper AST or lens.v2 payload; out of scope.")
            continue

        if passed:
            print(f"[PASS] {path} ({kind})")
        else:
            all_passed = False
            print(f"[FAIL] {path} ({kind}, {len(errors)} error(s)):")
            for error in errors:
                print(f"   - {error}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
