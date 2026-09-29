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

import difflib
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .bones import extract_bones

__all__ = [
    "BLEND_ROUTE_PATH",
    "BLEND_SEGMENT_BUDGET",
    "NODE_BLEND_ROUTE",
    "STOPWORDS",
    "TRIAGE_INTENTS",
    "RecommendationRouter",
    "RevisionBlender",
    "TopicAlignmentMatrix",
    "handle_node_blend_request",
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
        # [FEAT-627] Revision blending is the most specific operator in the
        # router: "blend" language is unambiguous, so it anchors ahead of every
        # other family rather than being stolen by `projection_request`'s
        # broader "revise" verb.
        "intent": "revision_blending",
        "handler": "RevisionBlender.blend_revisions",
        "verbs": (
            "blend", "merge revision", "merge these", "interleave", "crossbreed",
            "hybrid revision", "editorial dialogue", "candidate revision",
        ),
        "terms": (
            "blend", "blend revisions", "merge", "interleave", "hybrid", "gutter",
            "editorial dialogue", "dialogue", "candidate blend", "synthesize revision",
            "stamp",
        ),
    },
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


# ---------------------------------------------------------------------------
# [FEAT-627 / FEAT-618 / BKM-073] Revision blending -- editorial dialogue gutter
# ---------------------------------------------------------------------------
#
# BKM-073 coherence: a blend is a *candidate*, never an implicit version. The
# candidate is validated, then a human certifies it; only then does
# ``lens_service.register_blend_version`` mint v_{n+1}. Blends therefore never
# compound silently into the lineage (Oracle SPR-95 G2: quarantine, then
# certify -- never append an unvetted file to ``versions``).
#
# WIS-487 / SPR-95 audit section 2.2 mandate: CP-1 / CP-5 / CP-7 are NOT
# re-implemented here. The candidate is checked by importing the *existing*
# detectors -- ``curator.validate_paper_schema.validate_paper_ast`` for the
# structural gate and ``curator.annotate_resume_spine.verify_containment`` for
# truth-scoped numeric preservation and token containment. A bespoke detector
# in this module would fork the gate and guarantee drift, so there is
# deliberately no local CP logic.
#
# Hermeticity: this router answers in bounded time, so the check vocabulary
# (which numerics/tokens were lost) is read back from the shared detector's own
# report rather than re-parsed with a second local regex. No network, no LLM,
# no filesystem at import. The optional ``judge`` callable and the REST handler
# are the only seams that leave the module, and both are opt-in.

#: Canonical REST surface for the editorial dialogue gutter (Story 95.6).
BLEND_ROUTE_PATH = "/api/node/blend"
#: Hard cap on candidate segments, so a pathological input stays bounded.
BLEND_SEGMENT_BUDGET = 400
#: Deterministic segmenter: sentence-ish boundaries plus hard newlines.
_BLEND_SEGMENT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
#: A bare version reference (``v1``, ``v2_recruiter``), as opposed to prose.
_VERSION_REF_RE = re.compile(r"^v\d[a-z0-9_]*$", re.IGNORECASE)


def _blend_segments(text: Any) -> list[str]:
    """Split prose into deterministic, order-preserving segments.

    Segmentation is deliberately lexical (BKM-015): it decides where one
    candidate unit ends, not what the unit means.
    """
    if not isinstance(text, str):
        return []
    segments: list[str] = []
    for chunk in _BLEND_SEGMENT_RE.split(text):
        cleaned = chunk.strip()
        if cleaned:
            segments.append(cleaned)
        if len(segments) >= BLEND_SEGMENT_BUDGET:
            break
    return segments


def _normalized_segment(text: str) -> str:
    """Case/whitespace-folded segment identity, for deduplication only."""
    return " ".join(text.lower().split())


def _shared_detectors() -> tuple[Any, Any] | None:
    """Import the authoritative CP detectors at call time.

    Returns ``(validate_paper_ast, verify_containment)`` or ``None`` when the
    curator package is unreachable. ``None`` is *not* treated as a pass: the
    caller reports the gate as ``UNVERIFIED``, which blocks certification.
    """
    try:
        # Siblings at the top level of ``HomeLabAI/src``: ``projection`` and
        # ``curator`` are peer packages, so this is an absolute intra-src import
        # (the same shape ``annotate_resume_spine`` uses for ``projection.bones``).
        from curator.annotate_resume_spine import verify_containment
        from curator.validate_paper_schema import validate_paper_ast
    except (ImportError, OSError):  # pragma: no cover - both modules are local
        return None
    return validate_paper_ast, verify_containment


def _node_document(node_id: str, section_id: str, text: str, *, paper_id: str, revision_id: str) -> dict[str, Any]:
    """Build a minimal, valid single-node Paper AST for the shared gate.

    ``validate_paper_schema.validate_paper_ast`` and
    ``annotate_resume_spine.verify_containment`` both traverse the resume AST
    dialect, so a candidate that is only one node is expressed as a one-node
    document rather than as a special-case code path in the gate.
    """
    return {
        "paper_id": str(paper_id),
        "title": f"Blend candidate for {node_id}",
        "revision_id": str(revision_id),
        "metadata": {"revision_id": str(revision_id), "lens_applied": None},
        "sections": [
            {
                "section_id": str(section_id or "sec_blend"),
                "heading": str(section_id or "Blend"),
                "nodes": [{"node_id": str(node_id), "text": str(text)}],
            }
        ],
    }


def _token_diff(source_tokens: list[str], candidate_tokens: list[str]) -> dict[str, Any]:
    """Deterministic token-level diff between a source and the candidate.

    ``autojunk`` is disabled so the verdict never depends on the token
    frequency of the particular document (which would make CP evidence
    input-dependent rather than a pure function of the payload).
    """
    matcher = difflib.SequenceMatcher(a=source_tokens, b=candidate_tokens, autojunk=False)
    removed: list[str] = []
    added: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend(source_tokens[i1:i2])
        if tag in ("insert", "replace"):
            added.extend(candidate_tokens[j1:j2])
    return {
        "removed": removed,
        "added": added,
        "adds": len(added),
        "dels": len(removed),
        "unchanged": sum(i2 - i1 for tag, i1, i2, _j1, _j2 in matcher.get_opcodes() if tag == "equal"),
    }


class RevisionBlender:
    """Blend ``v_a`` and ``v_b`` into a certified candidate revision.

    Synthesis is deterministic and *superset-preserving* by default: the
    ``union`` mode (a) retains every source segment, (b) reorders them by
    lexical affinity to the human instruction and the active lens rubric, and
    (c) deduplicates identical segments. Because nothing is dropped, CP-1 token
    containment and CP-5 numeric preservation hold by construction. The
    ``compact`` mode intentionally drops low-affinity segments, which the
    shared gate is then free to reject -- the operator sees exactly what was
    lost instead of a silent metric regression.
    """

    def __init__(self, matrix: TopicAlignmentMatrix | None = None) -> None:
        self.matrix = matrix or TopicAlignmentMatrix()

    # -- judge seam ---------------------------------------------------------

    def build_judge_contract(
        self,
        paper_id: str,
        node_id: str,
        v_a: str,
        v_b: str,
        human_instruction: str = "",
        lens_id: str = "",
        rubric_terms: str = "",
        text_a: str = "",
        text_b: str = "",
    ) -> dict[str, Any]:
        """Structured prompt payload for an LLM editorial judge.

        Built unconditionally and hermetically, so the *contract* is always
        available even when no judge is wired. BKM-070 section 3 keeps the judge
        on the non-truth axis: it may propose stylistic synthesis, but the
        CP-1/CP-5/CP-7 verdicts below remain exclusively symbolic.
        """
        return {
            "contract": "revision_blend.v1",
            "feature": "FEAT-627",
            "paper_id": str(paper_id),
            "node_id": str(node_id),
            "lens_id": str(lens_id or ""),
            "sources": {
                "v_a": {"version_id": str(v_a), "text": str(text_a)},
                "v_b": {"version_id": str(v_b), "text": str(text_b)},
            },
            "human_instruction": str(human_instruction or ""),
            "rubric_terms": str(rubric_terms or ""),
            "system_directive": (
                "Synthesize one candidate revision for the named node that blends "
                "the qualities requested by the operator. Preserve every numeric "
                "literal present in either source verbatim (CP-5) and every source "
                "code token (CP-1). Do not invent achievements, metrics, or "
                "citations. Return prose only."
            ),
            "invariants": ["CP-1", "CP-5", "CP-7"],
            "adjudication": "symbolic-only (BKM-015); the judge has no vote on CP verdicts",
        }

    # -- synthesis ----------------------------------------------------------

    def _affinity(self, segment: str, instruction: str, rubric_terms: str) -> float:
        """Lexical affinity of a segment to the operator's intent.

        Reuses :class:`TopicAlignmentMatrix` -- the module's existing bounded
        containment scorer -- rather than introducing a second relevance metric.
        """
        guidance = f"{instruction or ''} {rubric_terms or ''}".strip()
        if not guidance:
            return 0.0
        return float(self.matrix.score_detail(segment, guidance)["score"])

    def synthesize(
        self,
        text_a: str,
        text_b: str,
        instruction: str = "",
        rubric_terms: str = "",
        mode: str = "union",
    ) -> dict[str, Any]:
        """Produce candidate text plus per-segment provenance.

        Returns a dict with ``candidate_text``, ``segments`` (ordered, tagged
        with origin and affinity) and ``guidance_applied`` -- never raises on
        malformed input.
        """
        if mode not in ("union", "compact"):
            mode = "union"

        a_segments = _blend_segments(text_a)
        b_segments = _blend_segments(text_b)

        # (origin, source_rank, text) in deterministic source order.
        entries: list[tuple[str, int, str]] = []
        for rank, seg in enumerate(a_segments):
            entries.append(("a", rank, seg))
        for rank, seg in enumerate(b_segments):
            entries.append(("b", rank, seg))

        # Deduplicate by folded identity. A segment present in both sources is
        # tagged "both": it is shared provenance, which is the strongest
        # possible evidence that the blend is faithful to both revisions.
        folded: dict[str, dict[str, Any]] = {}
        for origin, rank, seg in entries:
            key = _normalized_segment(seg)
            if not key:
                continue
            if key in folded:
                folded[key]["origins"].add(origin)
                continue
            folded[key] = {"text": seg, "origins": {origin}, "first_rank": rank}

        ranked: list[dict[str, Any]] = []
        for key, record in folded.items():
            affinity = self._affinity(record["text"], instruction, rubric_terms)
            if mode == "compact" and affinity <= 0.0:
                continue
            origins = record["origins"]
            ranked.append(
                {
                    "text": record["text"],
                    "origin": "both" if len(origins) > 1 else next(iter(origins)),
                    "affinity": round(affinity, 6),
                    "first_rank": record["first_rank"],
                }
            )

        # Most instruction-relevant first; stable on first appearance so the
        # ordering is fully reproducible for a given payload.
        ranked.sort(key=lambda item: (-item["affinity"], item["first_rank"]))

        segments = [item["text"] for item in ranked]
        candidate = " ".join(segments)

        if mode == "compact":
            candidate = self._restore_lost_numerics(candidate, ranked, a_segments, b_segments)

        return {
            "mode": mode,
            "candidate_text": candidate,
            "segments": [
                {
                    "index": index,
                    "origin": item["origin"],
                    "affinity": item["affinity"],
                    "text": item["text"],
                }
                for index, item in enumerate(ranked, start=1)
            ],
            "guidance_applied": bool((instruction or "").strip() or (rubric_terms or "").strip()),
            "source_segment_counts": {"v_a": len(a_segments), "v_b": len(b_segments)},
        }

    def _restore_lost_numerics(
        self,
        candidate: str,
        ranked: list[dict[str, Any]],
        a_segments: list[str],
        b_segments: list[str],
    ) -> str:
        """Bounded restoration pass for ``compact`` mode.

        The *authoritative* lost-literal set is read from the shared detector;
        source segments carrying those literals are re-admitted. Literal
        membership is decided by substring test, so no second numeric regex is
        introduced and the gate stays the single definition of "numeric".
        """
        detectors = _shared_detectors()
        if detectors is None:
            return candidate
        _validate_paper_ast, verify_containment = detectors

        present = {_normalized_segment(item["text"]) for item in ranked}
        pool = a_segments + b_segments

        for _ in range(4):  # bounded: each pass admits at least one new segment
            gate = verify_containment(
                _node_document("n", "s", " ".join(a_segments + b_segments), paper_id="blend", revision_id="source"),
                _node_document("n", "s", candidate, paper_id="blend", revision_id="candidate"),
            )
            lost = sorted(
                {
                    literal
                    for violation in gate["cp5_numeric_literals"]["violations"]
                    for literal in violation.get("lost_literals", [])
                }
            )
            if not lost:
                break
            admitted = False
            for literal in lost:
                for segment in pool:
                    if literal in segment and _normalized_segment(segment) not in present:
                        candidate = f"{candidate} {segment}".strip()
                        present.add(_normalized_segment(segment))
                        admitted = True
            if not admitted:
                break
        return candidate

    # -- validation (shared detectors only) ---------------------------------

    def validate_candidate(
        self,
        paper_id: str,
        node_id: str,
        candidate_text: str,
        source_text: str,
        section_id: str = "",
    ) -> dict[str, Any]:
        """Run the candidate through the existing CP gates.

        ``source_text`` is the concatenation of every source revision's prose
        for this node, so CP-5 asks the correct question: *did the blend drop a
        numeric literal that either parent carried?* (Oracle SPR-95 section 2.4:
        a blob diff against a mis-resolved origin reports false positives; the
        truth-scoped projector is the corrected detector.)
        """
        detectors = _shared_detectors()
        if detectors is None:
            return {
                "verdict": "UNVERIFIED",
                "passed": False,
                "reason": (
                    "curator.validate_paper_schema / curator.annotate_resume_spine "
                    "are unreachable; refusing to certify a candidate against a "
                    "gate that could not be loaded."
                ),
            }
        validate_paper_ast, verify_containment = detectors

        source_doc = _node_document(node_id, section_id, source_text, paper_id=paper_id, revision_id="source")
        candidate_doc = _node_document(node_id, section_id, candidate_text, paper_id=paper_id, revision_id="candidate")

        containment = verify_containment(source_doc, candidate_doc)
        structural_ok, structural_errors = validate_paper_ast(candidate_doc)

        cp1 = containment["cp1_token_containment"]
        cp5 = containment["cp5_numeric_literals"]
        passed = bool(structural_ok and cp1["passed"] and cp5["passed"])
        return {
            "verdict": "PASS" if passed else "FAIL",
            "passed": passed,
            "cp1_token_containment": cp1,
            "cp5_numeric_literals": cp5,
            "cp7_structural": {
                "passed": bool(structural_ok),
                "errors": list(structural_errors),
            },
        }

    # -- orchestration ------------------------------------------------------

    @staticmethod
    def next_version_id(versions: Any) -> str:
        """Return ``v_{n+1}`` from the registered lineage.

        Reads only the trailing integer of each version id, so a lineage of
        ``v1, v2_recruiter`` yields ``v3`` -- the next *milestone* number, not
        a per-lens compound id.
        """
        highest = 0
        for entry in _iter_version_entries(versions):
            match = re.match(r"^v(\d+)", str(entry.get("version_id", "")), re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
        return f"v{highest + 1}"

    @staticmethod
    def _resolve_revision_text(ref: Any, versions: Any) -> tuple[str | None, str]:
        """Resolve a revision reference to ``(text, reference_id)``.

        Accepts raw prose, a ``{"version_id", "text"}`` mapping, or a version id
        resolvable against ``versions`` (a mapping of id -> text, or a sequence
        of entries). Returns ``(None, ref)`` when a version id cannot be
        resolved -- the caller reports that rather than guessing at a text.
        """
        if isinstance(ref, Mapping):
            text = ref.get("text")
            version_id = str(ref.get("version_id") or ref.get("id") or "inline")
            return (str(text), version_id) if isinstance(text, str) else (None, version_id)

        if not isinstance(ref, str):
            return None, str(ref)

        if versions is not None:
            for entry in _iter_version_entries(versions):
                if str(entry.get("version_id")) == ref and isinstance(entry.get("text"), str):
                    return str(entry["text"]), ref
            if isinstance(versions, Mapping) and isinstance(versions.get(ref), str):
                return str(versions[ref]), ref

        if _VERSION_REF_RE.match(ref.strip()):
            return None, ref
        return ref, "inline"

    def blend_revisions(
        self,
        paper_id: str,
        node_id: str,
        v_a: Any,
        v_b: Any,
        human_instruction: str = "",
        lens_id: str = "",
        *,
        versions: Any = None,
        rubric_terms: str = "",
        mode: str = "union",
        judge: Callable[[dict[str, Any]], str] | None = None,
    ) -> dict[str, Any]:
        """Blend two revisions into a validated candidate.

        ``v_a`` / ``v_b`` accept raw prose, a ``{"version_id", "text"}`` mapping,
        or a version id resolvable against ``versions``. The default path is
        fully hermetic. When a ``judge`` callable is injected it is handed the
        structured contract from :meth:`build_judge_contract` and its return
        value is used as the candidate prose; the CP gates then run identically
        on that output, so an injected judge cannot bypass validation.
        """
        text_a, ref_a = self._resolve_revision_text(v_a, versions)
        text_b, ref_b = self._resolve_revision_text(v_b, versions)

        unresolved = [ref for ref, text in ((ref_a, text_a), (ref_b, text_b)) if text is None]
        if unresolved:
            return {
                "status": "unresolved_revision",
                "reason": (
                    "Version reference(s) could not be resolved to prose: "
                    f"{', '.join(unresolved)}. Pass the version text inline, or "
                    "supply `versions` carrying {version_id, text}."
                ),
                "paper_id": str(paper_id),
                "node_id": str(node_id),
            }

        assert text_a is not None and text_b is not None  # narrowed by unresolved check

        contract = self.build_judge_contract(
            paper_id, node_id, ref_a, ref_b, human_instruction, lens_id,
            rubric_terms=rubric_terms, text_a=text_a, text_b=text_b,
        )

        synthesis = self.synthesize(text_a, text_b, human_instruction, rubric_terms, mode)
        candidate_text = synthesis["candidate_text"]
        synthesis_source = "deterministic"

        if judge is not None:
            judged = judge(contract)
            if isinstance(judged, str) and judged.strip():
                candidate_text = judged.strip()
                synthesis_source = "judge"

        # Truth-scoped parent text: the union of both source revisions, so CP-5
        # asks whether the blend lost a metric either parent carried.
        source_text = f"{text_a} {text_b}".strip()
        cp = self.validate_candidate(paper_id, node_id, candidate_text, source_text)

        candidate_tokens = _tokenize(candidate_text)
        return {
            "status": "success",
            "feature": "FEAT-627",
            "paper_id": str(paper_id),
            "node_id": str(node_id),
            "v_a": ref_a,
            "v_b": ref_b,
            "lens_id": str(lens_id or ""),
            "instruction": str(human_instruction or ""),
            "mode": synthesis["mode"],
            "synthesis_source": synthesis_source,
            "candidate_text": candidate_text,
            "segments": synthesis["segments"],
            "guidance_applied": synthesis["guidance_applied"],
            "source_segment_counts": synthesis["source_segment_counts"],
            "diff": {
                "v_a": _token_diff(_tokenize(text_a), candidate_tokens),
                "v_b": _token_diff(_tokenize(text_b), candidate_tokens),
            },
            "cp": cp,
            "judge_contract": contract,
            "next_version_id": self.next_version_id(versions),
        }


def _iter_version_entries(versions: Any) -> Iterable[dict[str, Any]]:
    """Normalize a version collection into ``{version_id, text?}`` dicts."""
    if isinstance(versions, Mapping):
        for version_id, value in versions.items():
            if isinstance(value, Mapping):
                entry = dict(value)
                entry.setdefault("version_id", version_id)
                yield entry
            else:
                yield {"version_id": version_id, "text": value}
        return
    if isinstance(versions, (list, tuple)):
        for entry in versions:
            if isinstance(entry, Mapping):
                yield dict(entry)
            elif isinstance(entry, str):
                yield {"version_id": entry}


#: Router-manifest entry for ``POST /api/node/blend``. The foyer router imports
#: this descriptor rather than this module reaching into routing internals, so
#: the handler can be registered without the projection package importing the
#: daemon (and without a circular dependency).
NODE_BLEND_ROUTE: dict[str, Any] = {
    "path": BLEND_ROUTE_PATH,
    "methods": ("POST",),
    "handler": "projection.recommender.handle_node_blend_request",
    "feature": "FEAT-627",
}


def _blend_service() -> Any:
    """Load the IO-bearing curator service at call time.

    ``lens_service`` creates its data directories at *import* time; importing it
    at module scope would make this hermetic router touch the filesystem on
    import. The import therefore happens only when a REST call actually needs
    IO, and a failure degrades to an explicit error -- never to a fabricated
    version.
    """
    try:
        from curator import lens_service
    except (ImportError, OSError):  # pragma: no cover - module is local
        return None
    return lens_service


def handle_node_blend_request(payload: Mapping[str, Any] | None, *, service: Any = None) -> dict[str, Any]:
    """REST handler for ``POST /api/node/blend``.

    One route, two actions discriminated by ``action``:

    * ``blend`` (default) -- synthesize + validate a candidate. Returns the
      candidate text, segment provenance, diff highlights and the CP verdict.
    * ``stamp`` -- certify a candidate and mint ``v_{n+1}`` through the
      ``SpineManager``. The candidate is **re-validated server-side** before
      anything is written; a client-supplied "validated" flag is never trusted.

    Always returns a JSON-serializable dict carrying ``http_status``; never
    raises on malformed input.
    """
    if not isinstance(payload, Mapping):
        return {"status": "error", "error": "payload must be a JSON object", "http_status": 400}

    action = str(payload.get("action") or "blend").strip().lower()
    if action not in ("blend", "stamp"):
        return {
            "status": "error",
            "error": f"unsupported action '{action}'; expected 'blend' or 'stamp'",
            "http_status": 400,
        }

    missing = [key for key in ("paper_id", "node_id") if not str(payload.get(key) or "").strip()]
    if missing:
        return {
            "status": "error",
            "error": f"missing required field(s): {', '.join(missing)}",
            "http_status": 400,
        }

    svc = service or _blend_service()
    if svc is None:
        return {
            "status": "error",
            "error": "curator.lens_service unavailable; the blend IO channel cannot open",
            "http_status": 503,
        }

    if action == "stamp":
        result = _handle_stamp(payload, svc)
    else:
        result = _handle_blend(payload, svc)
    return result


def _handle_blend(payload: Mapping[str, Any], service: Any) -> dict[str, Any]:
    """Synthesize and validate a candidate (no writes)."""
    paper_id = str(payload.get("paper_id"))
    node_id = str(payload.get("node_id"))
    lens_id = str(payload.get("lens_id") or "")

    # Node-scoped lineage: each entry carries *this node's* prose per version,
    # so the blend compares the same coordinate across revisions rather than
    # whole-document blobs (Oracle SPR-95 section 2.4).
    versions = service.load_version_index(paper_id, node_id)
    version_ids = {str(entry.get("version_id")) for entry in _iter_version_entries(versions)}
    v_a = payload.get("v_a")
    v_b = payload.get("v_b")
    if v_a is None or v_b is None:
        return {"status": "error", "error": "v_a and v_b are required for a blend", "http_status": 400}
    for ref in (v_a, v_b):
        if isinstance(ref, str) and _VERSION_REF_RE.match(ref.strip()) and ref not in version_ids:
            return {
                "status": "error",
                "error": f"revision '{ref}' is not registered in the {paper_id} spine",
                "http_status": 404,
            }

    rubric_terms = service.load_rubric_terms(lens_id) if lens_id else ""
    result = RevisionBlender().blend_revisions(
        paper_id,
        node_id,
        v_a,
        v_b,
        str(payload.get("human_instruction") or ""),
        lens_id,
        versions=versions,
        rubric_terms=rubric_terms,
        mode=str(payload.get("mode") or "union"),
    )
    if result.get("status") != "success":
        result.setdefault("http_status", 422)
        return result
    result["http_status"] = 200
    return result


def _handle_stamp(payload: Mapping[str, Any], service: Any) -> dict[str, Any]:
    """Certify a candidate and register ``v_{n+1}`` into the SpineManager.

    Re-runs the shared CP gates against the lineage's own parent text, so a
    tampered or stale client candidate cannot enter the lineage.
    """
    paper_id = str(payload.get("paper_id"))
    node_id = str(payload.get("node_id"))
    candidate_text = payload.get("candidate_text")
    if not isinstance(candidate_text, str) or not candidate_text.strip():
        return {"status": "error", "error": "candidate_text is required to stamp", "http_status": 400}

    v_a = payload.get("v_a")
    v_b = payload.get("v_b")
    versions = service.load_version_index(paper_id, node_id)
    source_chunks: list[str] = []
    for ref in (v_a, v_b):
        text, _ref = RevisionBlender._resolve_revision_text(ref, versions)
        if text:
            source_chunks.append(text)
    if not source_chunks:
        return {
            "status": "error",
            "error": "cannot resolve v_a/v_b parent prose; refusing to stamp an ungrounded candidate",
            "http_status": 422,
        }

    cp = RevisionBlender().validate_candidate(paper_id, node_id, candidate_text, " ".join(source_chunks))
    if not cp["passed"]:
        return {
            "status": "rejected",
            "error": "candidate failed the CP gate; the lineage was not mutated",
            "cp": cp,
            "http_status": 409,
        }

    stamp = service.register_blend_version(
        paper_id=paper_id,
        node_id=node_id,
        candidate_text=candidate_text,
        parent_version=str(payload.get("parent_version") or ""),
        lens_id=str(payload.get("lens_id") or ""),
        instruction=str(payload.get("human_instruction") or ""),
    )
    stamp["cp"] = cp
    stamp["http_status"] = 200 if stamp.get("status") == "success" else 500
    return stamp
