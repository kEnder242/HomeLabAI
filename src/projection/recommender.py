#!/usr/bin/env python3
"""
[FEAT-603] Recommendation Router: Topic Triage, Alignment Matrix, Mutation
Proposals and Grounded Cover-Letter Synthesis.

Consolidated from:
  * HomeLabAI/src/recruiter.py (``NightlyRecruiter.calculate_semantic_match``,
    ``verify_and_score_jobs``, ``generate_brief``) -- the LLM-backed semantic
    scoring is retained *out of band*; the deterministic lexical scorer below
    provides the sub-millisecond pre-filter that keeps a routing loop from
    blocking on inference.
  * HomeLabAI/src/curator/lens_service.py (``expand_citations``) -- the
    citation-expansion intent family.

Design constraints:
  * Hermetic and deterministic. No network, no LLM, no filesystem. This module
    is a *routing adapter*, so it must answer in bounded time.
  * BKM-015: scoring is lexical token containment, never semantic grading. It
    is a triage pre-filter, not a judgement.
  * Cover letters are grounded exclusively in certified bone prose. When the
    evidence base is insufficient the synthesizer says so rather than
    fabricating achievement claims.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .bones import extract_bones

__all__ = [
    "STOPWORDS",
    "TRIAGE_INTENTS",
    "RecommendationRouter",
    "TopicAlignmentMatrix",
]

# Bounded vocabulary; lexical containment only.
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    ["a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those", "of", "in", "on", "at", "to", "for", "from", "by", "with", "without", "into", "over", "under", "across", "per", "as", "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "done", "have", "has", "had", "having", "it", "its", "we", "our", "you", "your", "they", "their", "he", "she", "his", "her", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "not", "no", "nor", "so", "such", "via", "about"]
)

# Intent families for triage. Each family declares:
#   * verbs -- high-signal tokens that anchor a match (matched as substrings so
#     "graded" still hits "grade"). Families are ordered most-specific-first,
#     so the first family with an anchored hit wins.
#   * terms -- the full vocabulary, reported back for operator transparency.
# Generic nouns ("section", "role", "application") are deliberately excluded
# from the anchor set: they are too common to route on their own.
TRIAGE_INTENTS: tuple[dict[str, Any], ...] = (
    {
        "intent": "cover_letter_synthesis",
        "handler": "RecommendationRouter.synthesize_cover_letter",
        "verbs": ("cover letter", "coverletter", "letter of interest", "why me", "cover", "letter"),
        "terms": (
            "cover letter", "coverletter", "cover-letter", "application letter",
            "letter of interest", "why me", "pitch me",
        ),
    },
    {
        "intent": "citation_expansion",
        "handler": "lens_service.expand_citations",
        "verbs": ("citation", "cite", "arxiv", "literature", "research anchor", "reference"),
        "terms": (
            "citation", "citations", "cite", "arxiv", "paper", "papers",
            "research anchor", "literature", "reference", "references",
        ),
    },
    {
        "intent": "lens_crafting",
        "handler": "projection.lenses.craft_lens",
        "verbs": ("lens", "rubric", "persona", "judge"),
        "terms": (
            "craft lens", "compile lens", "lens", "rubric", "persona", "judge",
        ),
    },
    {
        "intent": "bone_reconciliation",
        "handler": "projection.bones.reconcile_diff",
        "verbs": ("reconcile", "drift", "bone", "ast", "revision"),
        "terms": (
            "reconcile", "diff", "drift", "bone", "bones", "revision",
            "candidate", "ast", "section",
        ),
    },
    {
        "intent": "projection_request",
        "handler": "projection.engine.ProjectionEngine.project",
        "verbs": ("project", "grade", "revise", "polish", "rewrite"),
        "terms": (
            "project", "projection", "grade", "grading", "review flags",
            "revise", "polish", "rewrite",
        ),
    },
    {
        "intent": "topic_alignment",
        "handler": "TopicAlignmentMatrix.calculate_score",
        "verbs": ("alignment", "align", "match", "score", "jd"),
        "terms": (
            "alignment", "align", "match", "score", "fit", "jd", "job description",
            "requirement", "requirements", "role fit",
        ),
    },
    {
        "intent": "job_search",
        "handler": "recruiter.NightlyRecruiter",
        "verbs": ("job", "opening", "recruiter", "hiring", "interview", "apply"),
        "terms": (
            "job", "jobs", "role", "roles", "opening", "position", "recruiter",
            "application", "apply", "hiring", "interview",
        ),
    },
)


def _tokenize(text: Any) -> list[str]:
    """Lowercase ASCII word tokens, singularized, stopwords removed.

    Singularization is a naive trailing-``s`` strip. It is a lexical
    normalization step, not semantic analysis.
    """
    if not isinstance(text, str):
        return []
    tokens: list[str] = []
    for raw in _ASCII_WORD_RE.findall(text.lower()):
        token = raw[:-1] if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss") else raw
        if token in STOPWORDS or len(token) < 2:
            continue
        tokens.append(token)
    return tokens


def _token_set(text: Any) -> set[str]:
    return set(_tokenize(text))


def _iter_strings(value: Any) -> Iterable[str]:
    """Flatten str / list[str] / dict values / nested lists into strings."""
    if value is None:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _iter_strings(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_strings(nested)
    else:
        yield str(value)


class TopicAlignmentMatrix:
    """Deterministic topic-to-requirement alignment scorer.

    Combines three bounded lexical components:
      * ``coverage``  -- how much of the requirement vocabulary the topics cover
      * ``precision`` -- how much of the topic vocabulary the requirements justify
      * ``jaccard``   -- symmetric overlap, guards against padding topics

    The blended result is clamped to ``[0.0, 1.0]`` and rounded for
    reproducibility across platforms.
    """

    def __init__(self, coverage_weight: float = 0.6, precision_weight: float = 0.2) -> None:
        if coverage_weight < 0 or precision_weight < 0:
            raise ValueError("alignment weights must be non-negative")
        total = coverage_weight + precision_weight
        if total <= 0:
            raise ValueError("at least one alignment weight must be positive")
        self.coverage_weight = coverage_weight / total
        self.precision_weight = precision_weight / total

    def calculate_score(self, topics, requirements) -> float:
        """Score topical alignment in ``[0.0, 1.0]``.

        Accepts strings, or arbitrarily nested lists/dicts of strings, for both
        arguments. Returns ``0.0`` when either side has no usable tokens.
        """
        return round(self.score_detail(topics, requirements)["score"], 6)

    def score_detail(self, topics, requirements) -> dict[str, Any]:
        """Full component breakdown, for explainable routing decisions."""
        topic_tokens = _token_set(" ".join(_iter_strings(topics)))
        req_tokens = _token_set(" ".join(_iter_strings(requirements)))

        if not topic_tokens or not req_tokens:
            return {
                "score": 0.0,
                "coverage": 0.0,
                "precision": 0.0,
                "jaccard": 0.0,
                "matched": [],
                "unmatched_requirements": sorted(req_tokens),
                "topic_token_count": len(topic_tokens),
                "requirement_token_count": len(req_tokens),
            }

        matched = topic_tokens & req_tokens
        union = topic_tokens | req_tokens
        coverage = len(matched) / len(req_tokens)
        precision = len(matched) / len(topic_tokens)
        jaccard = len(matched) / len(union)

        score = min(1.0, self.coverage_weight * coverage + self.precision_weight * precision)
        return {
            "score": round(score, 6),
            "coverage": round(coverage, 6),
            "precision": round(precision, 6),
            "jaccard": round(jaccard, 6),
            "matched": sorted(matched),
            "unmatched_requirements": sorted(req_tokens - topic_tokens),
            "topic_token_count": len(topic_tokens),
            "requirement_token_count": len(req_tokens),
        }


class RecommendationRouter:
    """Deterministic triage router and grounded cover-letter synthesizer."""

    def __init__(self, matrix: TopicAlignmentMatrix | None = None) -> None:
        self.matrix = matrix or TopicAlignmentMatrix()

    # -- triage ------------------------------------------------------------

    def route_triage(self, query: str) -> dict[str, Any]:
        """Classify a free-text triage query into a served intent family.

        Returns a routing decision dict; never raises on malformed input. An
        unmatched query routes to ``general_triage`` with zero confidence so
        the caller can fall back rather than dead-end.
        """
        if not isinstance(query, str) or not query.strip():
            return {
                "status": "success",
                "query": query,
                "intent": "general_triage",
                "handler": None,
                "confidence": 0.0,
                "matched_terms": [],
                "query_tokens": [],
            }

        normalized = query.lower()
        tokens = set(_tokenize(query))

        for family in TRIAGE_INTENTS:
            # Anchored match: an anchor verb must appear in the query. Substring
            # matching is intentional so inflections ("graded", "grading") and
            # multi-word anchors ("cover letter") both land.
            anchors = [verb for verb in family["verbs"] if verb in normalized]
            if not anchors:
                continue
            hits = [term for term in family["terms"] if term in normalized]
            # Confidence blends anchor saturation with query-length dilution:
            # a short query hitting a single anchor is high-confidence, a long
            # query hitting the same anchor is discounted.
            saturation = min(1.0, len(anchors) / max(1, len(family["verbs"])))
            confidence = 0.5 + 0.5 * saturation
            confidence *= min(1.0, 0.6 + 0.1 * len(tokens))
            return {
                "status": "success",
                "query": query,
                "intent": family["intent"],
                "handler": family["handler"],
                "confidence": round(min(1.0, confidence), 6),
                "matched_terms": hits or anchors,
                "matched_anchors": anchors,
                "query_tokens": sorted(tokens),
            }

        return {
            "status": "success",
            "query": query,
            "intent": "general_triage",
            "handler": None,
            "confidence": 0.0,
            "matched_terms": [],
            "query_tokens": sorted(tokens),
        }

    # -- mutation proposals -------------------------------------------------

    def propose_mutations(self, review_flags: list[dict]) -> list[dict]:
        """Turn projection review flags into ordered, actionable mutations.

        Ordered by severity so a writer works the critical structural debt
        first. Pure function over flags; no document mutation is performed.
        """
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        actionable = [
            f for f in (review_flags or []) if isinstance(f, dict) and f.get("status") == "OPEN"
        ]
        actionable.sort(key=lambda f: (order.get(f.get("severity", "INFO"), 9), str(f.get("id", ""))))
        return [
            {
                "mutation_id": f"MUT-{index:03d}",
                "bone_id": f.get("bone_id"),
                "rule_id": f.get("rule_id"),
                "severity": f.get("severity"),
                "category": f.get("category"),
                "action": f.get("suggestion"),
                "status": "PROPOSED",
            }
            for index, f in enumerate(actionable, start=1)
        ]

    # -- cover letter -------------------------------------------------------

    def synthesize_cover_letter(self, bones, job_desc: str) -> str:
        """Compose a cover letter grounded exclusively in certified bone prose.

        Evidence lines are lifted verbatim from the strongest-matching bones.
        If no bone clears the grounding threshold the synthesizer returns an
        explicit insufficiency notice instead of inventing achievements.
        """
        job_tokens = _token_set(job_desc)
        if not job_tokens:
            return (
                "INSUFFICIENT GROUNDING: no job description supplied, so no "
                "evidence-backed letter can be synthesized."
            )

        scored: list[tuple[float, str, dict]] = []
        for bone in self._iter_bones(bones):
            for paragraph in bone.get("paragraphs", []) or []:
                text = str(paragraph).strip()
                if not text:
                    continue
                detail = self.matrix.score_detail(text, job_desc)
                if detail["score"] > 0:
                    scored.append((detail["score"], text, bone))

        if not scored:
            return (
                "INSUFFICIENT GROUNDING: none of the certified bones align with "
                "the supplied job description. Refusing to fabricate evidence."
            )

        # Deterministic ordering: score desc, then longest evidence first, then
        # bone id and text for full reproducibility.
        scored.sort(key=lambda item: (-item[0], -len(item[1]), str(item[2].get("bone_id", "")), item[1]))

        top = scored[:3]
        overall = min(1.0, sum(score for score, _, _ in top) / len(top))
        covered = set()
        for _, text, _ in top:
            covered |= _token_set(text) & job_tokens

        lines = [
            "Subject: Alignment of certified projection bones with target role",
            "",
            (
                "I am writing to apply for this role. The evidence below is drawn "
                "verbatim from my certified projection bones rather than "
                "reconstructed from memory."
            ),
            "",
            "EVIDENCE BASE:",
        ]
        for index, (_, text, bone) in enumerate(top, start=1):
            lines.append(f"{index}. {text}  [bone: {bone.get('bone_id', 'unknown')}]")
        lines += [
            "",
            "ALIGNMENT:",
            (
                f"- Target requirements addressed: {len(covered)}/{len(job_tokens)} "
                f"({overall:.2f} mean bone alignment)."
            ),
            f"- Highest-signal requirement: {min(sorted(covered)) if covered else 'n/a'}.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _iter_bones(bones) -> Iterable[dict]:
        """Accept a bone list, a bone envelope, or a raw document AST.

        A document AST (canonical or legacy paper-AST v1/v2) is normalized
        through ``extract_bones`` so that evidence grounding works identically
        regardless of which shape the caller holds.
        """
        if isinstance(bones, dict):
            if "bones" in bones:
                candidates = bones["bones"]
            elif "sections" in bones:
                # A document AST: reuse the canonical bone extractor rather
                # than re-deriving section prose here.
                candidates = extract_bones(bones)
            else:
                candidates = [bones]
        else:
            candidates = list(bones or [])

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if "paragraphs" in candidate or "bone_id" in candidate:
                yield candidate
                continue
            # A document AST section: synthesize a bone view for alignment.
            paragraphs = candidate.get("paragraphs") or []
            if not paragraphs:
                for node in candidate.get("nodes", []) or []:
                    if isinstance(node, dict) and node.get("text"):
                        paragraphs.append(str(node["text"]))
            if paragraphs:
                yield {
                    "bone_id": f"{candidate.get('paper_id', '')}::{candidate.get('section_id', '')}",
                    "paragraphs": paragraphs,
                }
