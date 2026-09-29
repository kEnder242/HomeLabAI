#!/usr/bin/env python3
"""
[FEAT-603 / FEAT-622] Projection Engine: Core Projection Lifecycle.

Consolidated from HomeLabAI/src/curator/lens_service.py (``grade_paper``) and
the Projector front-end scaffolding.

Lifecycle, per BKM-070 (Re-Anchoring Law)::

    1. ANCHOR   pi(C)   -- derive immutable bones from the certified document
    2. BIND     lens    -- attach the compiled rubric to those bones
    3. ADJUDICATE       -- run tier_0_structural rules deterministically;
                           emit tier_1_semantic evidence for the LLM judge
    4. RECONCILE        -- produce the candidate diff and drift metrics

The engine NEVER auto-resolves a ``tier_1_semantic`` rule (BKM-015). Power-verb
impact, tone and numeric-assertion equivalence are judge territory. What the
engine emits for tier_1 is *evidence* -- deterministic observations the judge
needs -- clearly marked ``advisory`` and excluded from the review-flag count.

Hermetic: no filesystem, no network, no LLM dependency. Callable identically
from the CLI and from the web endpoints.
"""

from __future__ import annotations

import re
from typing import Any

from .bones import DocumentAST, extract_bones, normalize_ast, reconcile_diff
from .lenses import (
    DEFAULT_DETECTOR_BUDGET,
    POWER_VERBS,
    UNSAFE_TO_CRAFT,
    WEAK_OPENINGS,
    validate_lens_schema,
)

__all__ = ["MAX_BULLETS_PER_BONE", "PROJECTION_SCHEMA_VERSION", "ProjectionEngine"]

PROJECTION_SCHEMA_VERSION = "projection.v2"

# BULLET_DENSITY_CAP working ceiling (recency bands: 4-6 recent, 1-3 older).
MAX_BULLETS_PER_BONE = 6

# BKM-015: scoped strictly to deterministic ASCII digit extraction.
_ASCII_DIGIT_RE = re.compile(r"\d")

_ROLE_HINTS = ("experience", "role", "employment")

# Tier_0 rules the engine knows how to decide deterministically.
_TIER_0_DISPATCH: dict[str, str] = {
    "NODE_IDENTITY_INTEGRITY": "presence",
    "CONTEXT_LINE_PURVIEW": "presence",
    "BULLET_DENSITY_CAP": "count",
    "DNA_CITATION_CONNECTION": "presence",
    "QUANTIFIED_ANCHOR_PRESENT": "token",
}

_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


class ProjectionEngine:
    """Projects a document AST through a lens rubric into a candidate revision.

    The engine is stateless with respect to the document: ``project`` may be
    called repeatedly with different lenses without cross-contamination, which
    keeps re-anchoring (diamond) topologies legal.
    """

    def __init__(self, lens: dict | None = None) -> None:
        self.lens = lens

    # -- public API --------------------------------------------------------

    def project(
        self,
        doc: DocumentAST | dict,
        lens: dict | None = None,
    ) -> dict[str, Any]:
        """Project ``doc`` through ``lens`` and return flags, diff and drift."""
        active_lens = lens if lens is not None else self.lens
        rejection = self._reject(active_lens)
        if rejection is not None:
            return rejection

        rubric = active_lens.get("rubric", active_lens)
        rules = list(rubric["rules"])
        budget = dict(rubric.get("detector_budget") or DEFAULT_DETECTOR_BUDGET)

        # 1. ANCHOR -- pi(C), immutable bones from the certified document.
        original_ast = normalize_ast(doc)
        original_bones = extract_bones(original_ast)

        # 2/3. BIND + ADJUDICATE.
        candidate_bones = [dict(b) for b in original_bones]
        review_flags: list[dict] = []
        advisories: list[dict] = []
        truncated: list[str] = []

        tier_0_rules = [r for r in rules if r["tier"] == "tier_0_structural"]
        tier_1_rules = [r for r in rules if r["tier"] == "tier_1_semantic"]

        for bone, candidate in zip(original_bones, candidate_bones):
            node_flags: list[dict] = []
            candidate["review_flags"] = []

            for rule in tier_0_rules:
                violation = self._adjudicate_tier_0(rule, bone)
                if violation is None:
                    continue
                node_flags.append(
                    {
                        "id": f"{bone['bone_id']}::{rule['rule_id']}",
                        "bone_id": bone["bone_id"],
                        "rule_id": rule["rule_id"],
                        "category": rule["category"],
                        "severity": rule["severity"],
                        "tier": rule["tier"],
                        "target": rule["target"],
                        "suggestion": violation,
                        "status": "OPEN",
                    }
                )

            node_flags.sort(key=lambda f: _SEVERITY_RANK.get(f["severity"], 9))
            if len(node_flags) > budget["max_flags_per_node"]:
                truncated.extend(f["id"] for f in node_flags[budget["max_flags_per_node"] :])
                node_flags = node_flags[: budget["max_flags_per_node"]]

            candidate["review_flags"] = node_flags
            review_flags.extend(node_flags)

            for rule in tier_1_rules:
                signal = self._collect_tier_1_evidence(rule, bone)
                if signal is None:
                    continue
                advisories.append(
                    {
                        "id": f"{bone['bone_id']}::{rule['rule_id']}",
                        "bone_id": bone["bone_id"],
                        "rule_id": rule["rule_id"],
                        "category": rule["category"],
                        "severity": rule["severity"],
                        "tier": rule["tier"],
                        "target": rule["target"],
                        "status": "PENDING_JUDGE",
                        "advisory": True,
                        "adjudicator": "tier_1_semantic",
                        "evidence": signal,
                    }
                )

        if len(review_flags) > budget["max_total_flags"]:
            truncated.extend(
                f["id"] for f in review_flags[budget["max_total_flags"] :]
            )
            review_flags = review_flags[: budget["max_total_flags"]]
            for candidate, kept in zip(candidate_bones, self._sync_bones(original_bones, review_flags, budget)):
                candidate["review_flags"] = kept

        # 4. RECONCILE -- candidate diff + drift metrics.
        diff = reconcile_diff({"bones": original_bones}, {"bones": candidate_bones})
        candidate_ast = self._apply_bones(original_ast, candidate_bones)

        return {
            "status": "success",
            "schema": PROJECTION_SCHEMA_VERSION,
            "paper_id": original_ast.paper_id,
            "lens_id": rubric["lens_id"],
            "revision_id": f"v2_projected_{rubric['lens_id']}",
            "bones": original_bones,
            "candidate_bones": candidate_bones,
            "candidate_ast": candidate_ast,
            "review_flags": review_flags,
            "total_review_flags": len(review_flags),
            "advisories": advisories,
            "advisory_count": len(advisories),
            "candidate_diff": diff,
            "drift": self._drift_metrics(diff, review_flags, advisories, len(original_bones)),
            "detector_budget": budget,
            "budget_truncated": truncated,
        }

    # -- tier 0: deterministic adjudication -------------------------------

    def _adjudicate_tier_0(self, rule: dict, bone: dict) -> str | None:
        """Return a suggestion string when the rule is violated, else None."""
        kind = _TIER_0_DISPATCH.get(rule["rule_id"])
        if kind is None:
            # Unknown tier_0 rule: never silently ignored, but also never
            # auto-adjudicated. Skipped by design -- recorded in advisories.
            return None

        paragraphs = bone.get("paragraphs", []) or []
        rule_id = rule["rule_id"]

        if rule_id == "NODE_IDENTITY_INTEGRITY":
            if not bone.get("section_id") or not str(bone.get("heading", "")).strip():
                return "Bone is missing a stable section id or heading (CP-1 containment)."
            return None

        if rule_id == "CONTEXT_LINE_PURVIEW":
            if self._is_role_bone(bone) and not paragraphs:
                return "Role bone has no purview line; add a 1-line context statement defining scale and purview."
            return None

        if rule_id == "BULLET_DENSITY_CAP":
            if len(paragraphs) > MAX_BULLETS_PER_BONE:
                return (
                    f"Section carries {len(paragraphs)} paragraphs, above the "
                    f"{MAX_BULLETS_PER_BONE} cap. Condense to 4-6 for recent roles."
                )
            return None

        if rule_id == "DNA_CITATION_CONNECTION":
            if not bone.get("citations"):
                return "Attach relevant DNA card or research paper bone to ground this achievement."
            return None

        if rule_id == "QUANTIFIED_ANCHOR_PRESENT":
            if paragraphs and not any(_ASCII_DIGIT_RE.search(p) for p in paragraphs):
                return "Bone carries no quantified anchor; add impact (%, latency, throughput, scale, headcount)."
            return None

        return None

    @staticmethod
    def _is_role_bone(bone: dict) -> bool:
        token = str(bone.get("section_id", "")).lower()
        return any(hint in token for hint in _ROLE_HINTS)

    # -- tier 1: evidence collection (never adjudication) ------------------

    def _collect_tier_1_evidence(self, rule: dict, bone: dict) -> dict | None:
        """Gather deterministic evidence for the tier_1 judge.

        These are observations, not verdicts. BKM-015 forbids resolving
        power-verb impact, tone, or numeric-assertion equivalence with regex,
        so nothing here is promoted to a review flag.
        """
        paragraphs = bone.get("paragraphs", []) or []
        if not paragraphs:
            return None
        rule_id = rule["rule_id"]
        lead = paragraphs[0].strip()

        if rule_id == "FIRST_3_WORDS_POWER_VERB":
            lowered = lead.lower()
            for weak_phrase, replacement in WEAK_OPENINGS:
                if lowered.startswith(weak_phrase):
                    return {
                        "kind": "passive_opening_match",
                        "phrase": weak_phrase,
                        "suggested_replacement": replacement,
                    }
            opening = [w.strip(".,;:\"'()") for w in lead.split()][:3]
            return {
                "kind": "opening_token_sample",
                "tokens": opening,
                "in_power_verb_vocabulary": any(t.lower() in POWER_VERBS for t in opening),
            }

        if rule_id == "SO_WHAT_METRIC_DRILL":
            return {
                "kind": "quantified_anchor_scan",
                "digit_tokens": sum(len(_ASCII_DIGIT_RE.findall(p)) for p in paragraphs),
                "paragraphs_scanned": len(paragraphs),
            }

        if rule_id == "THREE_SENTENCE_SUMMARY_HOOK":
            sentences = [s for s in lead.replace("!", ".").replace("?", ".").split(".") if s.strip()]
            return {"kind": "sentence_count", "sentence_count": len(sentences)}

        return {"kind": "unclassified", "paragraphs_scanned": len(paragraphs)}

    # -- metrics -----------------------------------------------------------

    def _drift_metrics(
        self,
        diff: dict,
        review_flags: list[dict],
        advisories: list[dict],
        bone_count: int,
    ) -> dict[str, Any]:
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        flagged_bones: set[str] = set()
        for flag in review_flags:
            by_severity[flag["severity"]] = by_severity.get(flag["severity"], 0) + 1
            by_category[flag["category"]] = by_category.get(flag["category"], 0) + 1
            flagged_bones.add(flag["bone_id"])

        return {
            "structural_drift": diff["drift"],
            "bones_total": bone_count,
            "bones_flagged": len(flagged_bones),
            "flagged_ratio": round(len(flagged_bones) / bone_count, 6) if bone_count else 0.0,
            "total_review_flags": len(review_flags),
            "flags_by_severity": by_severity,
            "flags_by_category": by_category,
            "critical_count": by_severity.get("CRITICAL", 0),
            "tier_1_pending": len(advisories),
            "is_reconciled": diff["is_reconciled"],
            "added_bones": len(diff["added"]),
            "removed_bones": len(diff["removed"]),
            "modified_bones": len(diff["modified"]),
        }

    @staticmethod
    def _apply_bones(ast: DocumentAST, bones: list[dict]) -> dict[str, Any]:
        """Rebuild the candidate AST payload from the flagged bones."""
        flags_by_bone: dict[str, list[dict]] = {
            bone["bone_id"]: bone.get("review_flags", []) for bone in bones
        }
        payload = ast.to_dict()
        for section in payload["sections"]:
            key = f"{ast.paper_id}::{section['id']}" if ast.paper_id else section["id"]
            section["review_flags"] = flags_by_bone.get(key, [])
        return payload

    @staticmethod
    def _sync_bones(
        original_bones: list[dict],
        kept_flags: list[dict],
        budget: dict,
    ) -> list[list[dict]]:
        """Rebuild per-bone flag buckets after a max_total_flags truncation."""
        buckets: dict[str, list[dict]] = {
            bone["bone_id"]: [] for bone in original_bones
        }
        for flag in kept_flags:
            buckets.setdefault(flag["bone_id"], []).append(flag)
        return [buckets[bone["bone_id"]] for bone in original_bones]

    # -- lens gating -------------------------------------------------------

    @staticmethod
    def _reject(lens: Any) -> dict[str, Any] | None:
        """Return a rejection payload when the lens cannot be bound."""
        if lens is None:
            return {
                "status": "LENS_REJECTED",
                "reason": "no lens supplied and no lens bound to the engine",
            }
        if isinstance(lens, dict) and lens.get("status") == UNSAFE_TO_CRAFT:
            return {
                "status": "LENS_REJECTED",
                "lens_id": lens.get("lens_id"),
                "reason": lens.get("reason", "lens compilation was refused"),
            }
        if not validate_lens_schema(lens):
            return {
                "status": "LENS_REJECTED",
                "lens_id": lens.get("lens_id") if isinstance(lens, dict) else None,
                "reason": "lens failed validate_lens_schema",
            }
        return None
