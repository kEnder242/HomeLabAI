#!/usr/bin/env python3
"""
[FEAT-603 / FEAT-622 / WIS-487] Synthesis Lens Compiler, Rule Validator &
Symbolic Rubric Detectors.

Consolidated from HomeLabAI/src/curator/lens_service.py (POWER_VERBS,
WEAK_OPENINGS, the 6 recruiter rubric rules and the craft_lens compiler).

Architectural mandates honoured here:
  * WIS-487 (Total Function Compilation): ``craft_lens`` performs *total*
    compilation. It either emits a fully valid, budget-respecting lens or it
    returns an ``UNSAFE_TO_CRAFT`` refusal carrying a machine-readable reason.
    It NEVER falls back to a silent default rubric.
  * BKM-015 (Parsing & Evaluation Taxonomy): rules are partitioned strictly:
      - ``tier_0_structural``  -- deterministic AST/JSON traversal. Presence,
        count, identity and ASCII token checks only. No natural-language
        grading, no power-verb judgement, no numeric assertion diffing.
      - ``tier_1_semantic``     -- adjudicated by an LLM judge at temperature=0
        with structured JSON output. These rules are *declarative only* in this
        module; the engine never auto-resolves them.
  * ``detector_budget`` caps the working set so a lens can never wedge the
    projection loop.
  * Class 1 design: ``craft_lens`` is hermetic (no filesystem, no network).
    Use :func:`persist_lens` for explicit, atomic persistence.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

__all__ = [
    "CATEGORIES",
    "DEFAULT_DETECTOR_BUDGET",
    "LENS_SCHEMA_VERSION",
    "MIN_CONTENT_CHARS",
    "POWER_VERBS",
    "SEVERITIES",
    "TIERS",
    "UNSAFE_TO_CRAFT",
    "WEAK_OPENINGS",
    "craft_lens",
    "persist_lens",
    "validate_lens_schema",
]

LENS_SCHEMA_VERSION = "lens.v2"
UNSAFE_TO_CRAFT = "UNSAFE_TO_CRAFT"
MIN_CONTENT_CHARS = 12

TIERS = ("tier_0_structural", "tier_1_semantic")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
CATEGORIES = ("PROSE", "REFINEMENT", "CONNECTION", "STRUCTURE")

# Working-set caps. Prevents a pathological lens from blocking execution loops.
DEFAULT_DETECTOR_BUDGET = {
    "tier_0": 32,
    "tier_1": 8,
    "max_flags_per_node": 16,
    "max_total_flags": 256,
}

# BKM-015: scoped to deterministic ASCII token extraction only (quantified
# anchor presence). It performs no semantic judgement.
_ASCII_DIGIT_RE = re.compile(r"\d")

# High-ownership verb vocabulary for ATS / recruiter rubrics. Consumed by the
# tier_1_semantic judge as a closed vocabulary, and exposed for adapter use.
POWER_VERBS = {
    "architected",
    "spearheaded",
    "engineered",
    "directed",
    "standardized",
    "deployed",
    "authored",
    "audited",
    "established",
    "restructured",
    "mentored",
    "optimized",
    "synthesized",
    "profiled",
    "developed",
    "saved",
    "led",
    "automated",
    "built",
    "implemented",
    "partnered",
    "validated",
    "drove",
    "orchestrated",
    "pioneered",
    "scaled",
    "eliminated",
    "recovered",
    "reimagined",
    "launched",
    "founded",
    "migrated",
    "hardened",
    "accelerated",
}

# (weak_phrase, replacement) -- passive openings that signal zero ownership.
WEAK_OPENINGS = [
    ("worked on", "Architected / Engineered"),
    ("responsible for", "Directed / Spearheaded"),
    ("helped with", "Standardized / Facilitated"),
    ("helped", "Co-engineered / Supported"),
    ("assisted with", "Validated / Executed"),
    ("participated in", "Collaborated on / Drove"),
]

DEFAULT_PERSONA = {
    "name": "Farah Sharghi (Recruiter Lens)",
    "role": "Principal Recruiter & Talent Architect",
    "lens_perspective": "Pragmatic hiring manager scanning for high-signal proof points",
}

# tier_0 -> decidable by deterministic AST traversal alone.
# tier_1 -> declarative only; adjudicated by the LLM judge.
_BASE_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "NODE_IDENTITY_INTEGRITY",
        "category": "STRUCTURE",
        "target": "document_node",
        "severity": "CRITICAL",
        "tier": "tier_0_structural",
        "description": "Every bone must resolve to a non-empty stable id and heading (CP-1 token containment).",
    },
    {
        "rule_id": "CONTEXT_LINE_PURVIEW",
        "category": "REFINEMENT",
        "target": "role_header",
        "severity": "MEDIUM",
        "tier": "tier_0_structural",
        "description": "Include a single 1-line context statement beneath the title and company defining team scale and direct purview before bullets appear.",
    },
    {
        "rule_id": "BULLET_DENSITY_CAP",
        "category": "STRUCTURE",
        "target": "section_structure",
        "severity": "MEDIUM",
        "tier": "tier_0_structural",
        "description": "Recent roles: 4-6 bullets max. Older roles: 1-3 bullets max.",
    },
    {
        "rule_id": "DNA_CITATION_CONNECTION",
        "category": "CONNECTION",
        "target": "bone_citations",
        "severity": "INFO",
        "tier": "tier_0_structural",
        "description": "Attach corresponding DNA cards or arXiv research anchors where empirical validation occurred.",
    },
    {
        "rule_id": "QUANTIFIED_ANCHOR_PRESENT",
        "category": "REFINEMENT",
        "target": "bone_paragraphs",
        "severity": "MEDIUM",
        "tier": "tier_0_structural",
        "description": "Each bone must carry at least one quantified anchor (ASCII digit token).",
    },
    {
        "rule_id": "FIRST_3_WORDS_POWER_VERB",
        "category": "PROSE",
        "target": "bullet_opening",
        "severity": "CRITICAL",
        "tier": "tier_1_semantic",
        "description": "Start every bullet with a high-impact power verb signaling direct ownership. Avoid passive openings like 'Responsible for' or 'Worked on'. Adjudicated by the LLM judge against the POWER_VERBS vocabulary.",
    },
    {
        "rule_id": "SO_WHAT_METRIC_DRILL",
        "category": "REFINEMENT",
        "target": "bone_paragraphs",
        "severity": "HIGH",
        "tier": "tier_1_semantic",
        "description": "Every bullet must pass the 'So What?' test by tying the task to operational or business impact (%, latency, throughput, scale, headcount). Numeric assertion equivalence is judge-resolved, never regex-resolved.",
    },
    {
        "rule_id": "THREE_SENTENCE_SUMMARY_HOOK",
        "category": "PROSE",
        "target": "summary_section",
        "severity": "HIGH",
        "tier": "tier_1_semantic",
        "description": "Summary must be approximately 3 sentences: Identity & Purview, Differentiator / Superpower, and Macro Career Proof Point.",
    },
)

# Order-preserving de-duplication of user-supplied criteria.
_RULE_FIELDS = ("rule_id", "category", "target", "severity", "tier", "description")


def _refuse(lens_id: str, reason: str) -> dict[str, Any]:
    """WIS-487: total refusal. Never raises, never falls back to defaults."""
    return {
        "status": UNSAFE_TO_CRAFT,
        "lens_id": lens_id,
        "reason": reason,
        "schema": LENS_SCHEMA_VERSION,
    }


def _coerce_criteria(criteria: Any, lens_id: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Validate caller-supplied criteria. Returns (rules, refusal_reason)."""
    if criteria is None:
        return [], None
    if not isinstance(criteria, list):
        return None, f"criteria must be a list, got {type(criteria).__name__}"

    coerced: list[dict[str, Any]] = []
    for index, item in enumerate(criteria):
        if not isinstance(item, dict):
            return None, f"criteria[{index}] must be a dict, got {type(item).__name__}"
        rule_id = str(item.get("rule_id", "")).strip()
        if not rule_id:
            return None, f"criteria[{index}] is missing a non-empty 'rule_id'"
        severity = str(item.get("severity", "MEDIUM")).upper()
        if severity not in SEVERITIES:
            return None, f"criteria[{index}] has unknown severity '{severity}'"
        tier = str(item.get("tier", "tier_1_semantic"))
        if tier not in TIERS:
            return None, f"criteria[{index}] has unknown tier '{tier}'"
        coerced.append(
            {
                "rule_id": rule_id,
                "category": str(item.get("category", "REFINEMENT")).upper(),
                "target": str(item.get("target", "bone_paragraphs")),
                "severity": severity,
                "tier": tier,
                "description": str(item.get("description", "")),
            }
        )
    return coerced, None


def craft_lens(
    lens_id: str,
    content: str,
    title: str = None,
    persona: dict = None,
    criteria: list = None,
) -> dict:
    """Compile advice text or a job description into a structured lens rubric.

    Returns either a compiled lens dict (``status == "success"``) or a refusal
    dict (``status == "UNSAFE_TO_CRAFT"``) carrying ``lens_id`` and ``reason``.

    This function is hermetic -- it performs no filesystem or network I/O.
    Call :func:`persist_lens` to write the compiled lens atomically.
    """
    # --- Gate 1: lens identity -------------------------------------------
    if not isinstance(lens_id, str) or not lens_id.strip():
        return _refuse(str(lens_id), "lens_id must be a non-empty string")
    lens_id = lens_id.strip()

    # --- Gate 2: source content (WIS-487 refusal branch) ------------------
    if content is None or not isinstance(content, str):
        return _refuse(
            lens_id, f"content must be a string, got {type(content).__name__}"
        )
    stripped = content.strip()
    if not stripped:
        return _refuse(lens_id, "content is empty; refusing to craft a rubric from nothing")
    if len(stripped) < MIN_CONTENT_CHARS:
        return _refuse(
            lens_id,
            f"content is too short to yield a rubric: {len(stripped)} chars "
            f"(minimum {MIN_CONTENT_CHARS})",
        )

    # --- Gate 3: optional inputs (no silent coercion) --------------------
    coerced_criteria, refusal = _coerce_criteria(criteria, lens_id)
    if refusal is not None:
        return _refuse(lens_id, refusal)
    if persona is not None and not isinstance(persona, dict):
        return _refuse(
            lens_id, f"persona must be a dict, got {type(persona).__name__}"
        )
    if title is not None and not isinstance(title, str):
        return _refuse(lens_id, f"title must be a str, got {type(title).__name__}")

    # --- Compile: order-preserving, de-duplicated rule assembly ----------
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in (*_BASE_RULES, *(coerced_criteria or [])):
        if rule["rule_id"] in seen:
            continue
        seen.add(rule["rule_id"])
        rules.append({k: rule[k] for k in _RULE_FIELDS})

    # --- Enforce detector budget explicitly (never silently) -------------
    budget = dict(DEFAULT_DETECTOR_BUDGET)
    tier_0 = [r for r in rules if r["tier"] == "tier_0_structural"]
    tier_1 = [r for r in rules if r["tier"] == "tier_1_semantic"]

    budget_exceeded: list[str] = []
    if len(tier_0) > budget["tier_0"]:
        dropped = tier_0[budget["tier_0"]:]
        budget_exceeded.extend(r["rule_id"] for r in dropped)
        rules = [r for r in rules if r["rule_id"] not in {d["rule_id"] for d in dropped}]
    if len(tier_1) > budget["tier_1"]:
        dropped = tier_1[budget["tier_1"]:]
        budget_exceeded.extend(r["rule_id"] for r in dropped)
        rules = [r for r in rules if r["rule_id"] not in {d["rule_id"] for d in dropped}]

    compiled_persona = dict(DEFAULT_PERSONA)
    if persona:
        compiled_persona.update(persona)

    rubric = {
        "schema": LENS_SCHEMA_VERSION,
        "lens_id": lens_id,
        "title": (title or lens_id.replace("_", " ").title()).strip(),
        "persona": compiled_persona,
        "source_snippet": stripped[:300],
        "source_chars": len(stripped),
        "rules": rules,
        "rubric_rules": rules,
        "tier_manifest": {
            "tier_0_structural": [r["rule_id"] for r in rules if r["tier"] == "tier_0_structural"],
            "tier_1_semantic": [r["rule_id"] for r in rules if r["tier"] == "tier_1_semantic"],
        },
        "detector_budget": budget,
        "judge_contract": {
            "temperature": 0,
            "output": "structured_json",
            "resolves": "tier_1_semantic",
        },
        "budget_exceeded": budget_exceeded,
    }

    if not validate_lens_schema(rubric):
        # Self-verification gate: a compiled lens must always validate.
        return _refuse(lens_id, "compiled lens failed its own schema validation")

    return {"status": "success", "lens_id": lens_id, "rubric": rubric}


def validate_lens_schema(lens: dict) -> bool:
    """Validate a lens (or a craft_lens envelope) against LENS_SCHEMA_VERSION.

    Returns False for any structural violation; never raises.
    """
    if not isinstance(lens, dict):
        return False
    if lens.get("status") == UNSAFE_TO_CRAFT:
        return False

    rubric = lens.get("rubric", lens)
    if not isinstance(rubric, dict):
        return False

    for key in ("schema", "lens_id", "title", "persona", "rules", "detector_budget"):
        if key not in rubric:
            return False
    if not isinstance(rubric["lens_id"], str) or not rubric["lens_id"].strip():
        return False
    if not isinstance(rubric["title"], str) or not rubric["title"].strip():
        return False
    if not isinstance(rubric["persona"], dict):
        return False

    rules = rubric["rules"]
    if not isinstance(rules, list) or not rules:
        return False

    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            return False
        for key in _RULE_FIELDS:
            if key not in rule:
                return False
        if not isinstance(rule["rule_id"], str) or not rule["rule_id"].strip():
            return False
        if rule["rule_id"] in seen:
            return False
        seen.add(rule["rule_id"])
        if rule["severity"] not in SEVERITIES:
            return False
        if rule["category"] not in CATEGORIES:
            return False
        if rule["tier"] not in TIERS:
            return False

    # CP-1: no tier_0 rule may smuggle semantic grading. Tier_0 is decidable
    # by deterministic traversal only, so semantic rule ids are barred there.
    SEMANTIC_ONLY_RULES = {
        "FIRST_3_WORDS_POWER_VERB",
        "SO_WHAT_METRIC_DRILL",
        "THREE_SENTENCE_SUMMARY_HOOK",
    }
    for rule in rules:
        if rule["tier"] == "tier_0_structural" and rule["rule_id"] in SEMANTIC_ONLY_RULES:
            return False

    budget = rubric["detector_budget"]
    if not isinstance(budget, dict):
        return False
    for key in ("tier_0", "tier_1", "max_flags_per_node", "max_total_flags"):
        if not isinstance(budget.get(key), int) or budget[key] <= 0:
            return False

    tier_0_count = sum(1 for r in rules if r["tier"] == "tier_0_structural")
    tier_1_count = sum(1 for r in rules if r["tier"] == "tier_1_semantic")
    if tier_0_count > budget["tier_0"] or tier_1_count > budget["tier_1"]:
        return False

    manifest = rubric.get("tier_manifest")
    if manifest is not None:
        if not isinstance(manifest, dict):
            return False
        if set(manifest.keys()) != set(TIERS):
            return False

    return True


def persist_lens(lens: dict, directory: str | os.PathLike) -> str:
    """Atomically persist a compiled lens as ``<lens_id>.json``.

    Explicit I/O, separated from the hermetic compiler per Class 1 design and
    the production/runtime decoupling mandate.
    """
    if not isinstance(lens, dict) or lens.get("status") != "success":
        raise ValueError("persist_lens requires a compiled lens with status 'success'")
    rubric = lens["rubric"]
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / f"{rubric['lens_id']}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(rubric, indent=2), encoding="utf-8")
    os.replace(tmp_path, out_path)
    return str(out_path)
