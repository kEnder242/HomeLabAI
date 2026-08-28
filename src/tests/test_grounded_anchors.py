"""
[FEAT-483] Grounded Validation Anchor Test Suite (VAL-01–VAL-10)

Parameterized tests over config/validation_anchors.json that verify:
    1. Every anchor query bypasses _GREETING_RE and _WYWO_RE fast-paths.
    2. Queries resolve to genuine policy vibes with correct domain mappings
       via TriagePolicyLoader.
    3. VAL-01–VAL-07 define active RAG rules with target collections;
       zero-context conversational/supervisory turns omit RAG.
    4. Keyword coverage against expected_keywords per anchor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Path setup – mirror the convention in sibling test modules
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # HomeLabAI/
_ANCHORS_PATH = _REPO_ROOT / "config" / "validation_anchors.json"
_POLICY_PATH = _REPO_ROOT / "config" / "triage_policy.json"

from src.logic.triage_engine import (
    _GREETING_RE,
    _WYWO_RE,
    classify_vibe_and_domain,
)
from src.logic.triage_policy_loader import TriagePolicyLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anchors() -> list[dict[str, Any]]:
    """Load all validation anchors from config."""
    with open(_ANCHORS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def policy_loader() -> TriagePolicyLoader:
    """Return a TriagePolicyLoader backed by the production policy."""
    loader = TriagePolicyLoader(policy_path=str(_POLICY_PATH))
    loader.load_policy()
    return loader


# ---------------------------------------------------------------------------
# Expected vibe→domain mapping per anchor
#
# The anchor "domain" field (silicon_validation, platform_telemetry,
# lab_architecture) is the *source* domain.  The triage policy defines
# a `default_domain` per vibe.  These are the expected vibe assignments
# derived from the query semantics and ground_truth_summaries.
# ---------------------------------------------------------------------------
_EXPECTED_VIBE_MAP: dict[str, tuple[str, str]] = {
    # silicon_validation anchors → TECHNICAL (exp_tlm)
    "VAL-01": ("TECHNICAL", "exp_tlm"),
    "VAL-02": ("TECHNICAL", "exp_tlm"),
    "VAL-03": ("TECHNICAL", "exp_tlm"),
    # silicon_validation – historical engineering → HISTORICAL (lab_history)
    "VAL-04": ("HISTORICAL", "lab_history"),
    # platform_telemetry anchors → TECHNICAL (exp_tlm)
    "VAL-05": ("TECHNICAL", "exp_tlm"),
    "VAL-06": ("TECHNICAL", "exp_tlm"),
    # platform_telemetry – SRE/operational → OPERATIONAL (exp_bkm)
    "VAL-07": ("OPERATIONAL", "exp_bkm"),
    # lab_architecture anchors → META (feedback)
    # [FEAT-487 / SPR-65] META's canonical default_domain is now feedback (supervisory /
    # control-plane feedback loop). lab_internal meta-status routing is preserved at
    # runtime via _META_DOMAIN_OVERRIDES in triage_engine, not via META's default_domain.
    "VAL-08": ("META", "feedback"),
    "VAL-09": ("META", "feedback"),
    "VAL-10": ("META", "feedback"),
}


def _anchor_ids() -> list[str]:
    """Return sorted list of anchor IDs for parametrize."""
    return sorted(_EXPECTED_VIBE_MAP.keys())


def _keyword_present(keyword: str, corpus_lower: str) -> bool:
    """Check if a keyword is present in the corpus (case-insensitive).

    Handles multi-word keywords and underscore-delimited symbols by checking
    both the full keyword and each constituent word individually.  This
    accommodates abbreviations (e.g. "UE Status" → both "ue" and "status")
    and underscored identifiers (e.g. "backing_dev_info" → "backing", "dev",
    "info").
    """
    if keyword.lower() in corpus_lower:
        return True
    # Split on spaces and underscores, check every constituent word
    import re as _re
    words = _re.split(r"[\s_]+", keyword)
    return all(w.lower() in corpus_lower for w in words if w)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Fast-path bypass – no anchor query may match greeting/WYWO regex
# ═══════════════════════════════════════════════════════════════════════════


class TestFastPathBypass:
    """Every grounded anchor must bypass the CASUAL and WYWO fast-paths."""

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_bypasses_greeting_regex(self, anchor_id: str, anchors: list[dict[str, Any]]) -> None:
        """Anchor query must NOT match _GREETING_RE."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        query = anchor["query"]
        assert _GREETING_RE.search(query) is None, (
            f"{anchor_id} unexpectedly matched _GREETING_RE – "
            "grounded anchors must bypass the CASUAL fast-path"
        )

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_bypasses_wywo_regex(self, anchor_id: str, anchors: list[dict[str, Any]]) -> None:
        """Anchor query must NOT match _WYWO_RE."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        query = anchor["query"]
        assert _WYWO_RE.search(query) is None, (
            f"{anchor_id} unexpectedly matched _WYWO_RE – "
            "grounded anchors must bypass the WYWO fast-path"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Vibe / domain resolution via TriagePolicyLoader
# ═══════════════════════════════════════════════════════════════════════════


class TestVibeDomainResolution:
    """Each anchor query must resolve to a genuine policy vibe and domain."""

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_resolves_to_genuine_vibe(
        self, anchor_id: str, anchors: list[dict[str, Any]], policy_loader: TriagePolicyLoader
    ) -> None:
        """classify_vibe_and_domain returns a vibe that exists in the policy."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        expected_vibe, _expected_domain = _EXPECTED_VIBE_MAP[anchor_id]

        # Provide a parsed_json that carries the expected vibe as the LLM
        # would return – classify_vibe_and_domain should pass it through.
        parsed_json = {"vibe": expected_vibe, "domain": "standard"}

        vibe, _domain = classify_vibe_and_domain(
            anchor["query"], parsed_json, policy_loader=policy_loader
        )

        # The vibe must be a known, enabled policy vibe
        rule = policy_loader.get_vibe_rule(vibe)
        assert rule is not None, (
            f"{anchor_id}: vibe '{vibe}' not found in triage policy"
        )

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_policy_domain_mapping(
        self, anchor_id: str, policy_loader: TriagePolicyLoader
    ) -> None:
        """TriagePolicyLoader maps each expected vibe to the correct default_domain."""
        expected_vibe, expected_domain = _EXPECTED_VIBE_MAP[anchor_id]
        rule = policy_loader.get_vibe_rule(expected_vibe)
        assert rule is not None, (
            f"Vibe '{expected_vibe}' (for {anchor_id}) absent from policy"
        )
        actual_domain = rule.get("default_domain")
        assert actual_domain == expected_domain, (
            f"{anchor_id}: vibe '{expected_vibe}' default_domain "
            f"expected '{expected_domain}', got '{actual_domain}'"
        )

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_policy_loader_confirms_vibe_enabled(
        self, anchor_id: str, policy_loader: TriagePolicyLoader
    ) -> None:
        """The expected vibe is present and enabled in the policy."""
        expected_vibe, _ = _EXPECTED_VIBE_MAP[anchor_id]
        rule = policy_loader.get_vibe_rule(expected_vibe)
        assert rule is not None, (
            f"Vibe '{expected_vibe}' (for {anchor_id}) absent from policy"
        )
        assert rule.get("enabled") is True, (
            f"Vibe '{expected_vibe}' (for {anchor_id}) is disabled"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. RAG configuration – VAL-01–07 must have active RAG; conversational
#    turns (VAL-08–10 = META/lab_architecture) omit RAG
# ═══════════════════════════════════════════════════════════════════════════


class TestRagConfiguration:
    """VAL-01–VAL-07 define active RAG rules; VAL-08–VAL-10 omit RAG."""

    _RETRIEVAL_IDS = [f"VAL-{i:02d}" for i in range(1, 8)]   # VAL-01 … VAL-07
    _ZERO_CONTEXT_IDS = [f"VAL-{i:02d}" for i in range(8, 11)]  # VAL-08 … VAL-10

    @pytest.mark.parametrize("anchor_id", _RETRIEVAL_IDS)
    def test_retrieval_anchor_has_rag(
        self, anchor_id: str, anchors: list[dict[str, Any]], policy_loader: TriagePolicyLoader
    ) -> None:
        """VAL-01–07: target vibe must carry an active RAG config with collections."""
        expected_vibe, _ = _EXPECTED_VIBE_MAP[anchor_id]
        rag = policy_loader.get_rag_config(expected_vibe)
        assert rag is not None, (
            f"{anchor_id}: vibe '{expected_vibe}' has no RAG config – "
            "retrieval anchors must define active RAG"
        )
        assert isinstance(rag, dict), (
            f"{anchor_id}: RAG config must be a dict, got {type(rag).__name__}"
        )

    @pytest.mark.parametrize("anchor_id", _RETRIEVAL_IDS)
    def test_retrieval_anchor_has_target_collections(
        self, anchor_id: str, anchors: list[dict[str, Any]], policy_loader: TriagePolicyLoader
    ) -> None:
        """VAL-01–07: RAG config must list at least one allowed collection."""
        expected_vibe, _ = _EXPECTED_VIBE_MAP[anchor_id]
        rag = policy_loader.get_rag_config(expected_vibe)
        assert rag is not None
        collections = rag.get("allowed_collections")
        assert isinstance(collections, list) and len(collections) > 0, (
            f"{anchor_id}: vibe '{expected_vibe}' RAG must define "
            "a non-empty allowed_collections list"
        )

    @pytest.mark.parametrize("anchor_id", _ZERO_CONTEXT_IDS)
    def test_zero_context_anchor_omits_rag(
        self, anchor_id: str, anchors: list[dict[str, Any]], policy_loader: TriagePolicyLoader
    ) -> None:
        """VAL-08–10: conversational/supervisory vibes must omit RAG entirely."""
        expected_vibe, _ = _EXPECTED_VIBE_MAP[anchor_id]
        rag = policy_loader.get_rag_config(expected_vibe)
        # get_rag_config returns None when rag key is absent or explicitly null
        assert rag is None, (
            f"{anchor_id}: vibe '{expected_vibe}' unexpectedly defines RAG "
            f"({rag}) – zero-context turns must omit RAG"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Keyword coverage – each anchor's query + ground_truth_summary must
#    contain every expected keyword
# ═══════════════════════════════════════════════════════════════════════════


class TestKeywordCoverage:
    """Every expected_keyword must appear in the query or ground_truth_summary."""

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_keywords_present(self, anchor_id: str, anchors: list[dict[str, Any]]) -> None:
        """All expected_keywords are present in anchor text (word-level matching)."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        corpus = f"{anchor['query']} {anchor['ground_truth_summary']}".lower()
        missing = [kw for kw in anchor["expected_keywords"]
                   if not _keyword_present(kw, corpus)]
        assert not missing, (
            f"{anchor_id}: missing keywords {missing} "
            f"in query/ground_truth corpus"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Anchor structural integrity – config file sanity
# ═══════════════════════════════════════════════════════════════════════════


class TestAnchorIntegrity:
    """Validation anchors config must contain exactly 10 well-formed entries."""

    def test_anchor_count(self, anchors: list[dict[str, Any]]) -> None:
        """Exactly 10 anchors (VAL-01 through VAL-10) must be defined."""
        assert len(anchors) == 10

    def test_sequential_ids(self, anchors: list[dict[str, Any]]) -> None:
        """Anchor IDs must be sequential VAL-01 through VAL-10."""
        ids = [a["id"] for a in anchors]
        expected = [f"VAL-{i:02d}" for i in range(1, 11)]
        assert ids == expected

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_required_fields(self, anchor_id: str, anchors: list[dict[str, Any]]) -> None:
        """Each anchor must define id, query, domain, target_collection, expected_keywords."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        for field in ("id", "query", "domain", "target_collection", "expected_keywords"):
            assert field in anchor, f"{anchor_id}: missing required field '{field}'"
            assert anchor[field], f"{anchor_id}: field '{field}' is empty"

    @pytest.mark.parametrize("anchor_id", _anchor_ids())
    def test_keywords_nonempty(self, anchor_id: str, anchors: list[dict[str, Any]]) -> None:
        """expected_keywords must be a non-empty list."""
        anchor = next(a for a in anchors if a["id"] == anchor_id)
        kw = anchor["expected_keywords"]
        assert isinstance(kw, list) and len(kw) > 0, (
            f"{anchor_id}: expected_keywords must be a non-empty list"
        )
