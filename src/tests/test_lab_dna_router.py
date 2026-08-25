"""
[FEAT-469] Unit Tests for Lab DNA Router Satellite

Covers:
    1. get_collection_priorities – META/lab_internal routing, lab_history, default
    2. filter_candidate_context – Zero Context gate, suppression, distance sorting
    3. format_lab_dna_tag – FEATURE_DNA, INFRA, BKM, fallback tags
"""

from __future__ import annotations

from src.nodes.lab_dna_router import (
    filter_candidate_context,
    format_lab_dna_tag,
    get_collection_priorities,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. get_collection_priorities
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCollectionPriorities:
    """Collection routing by vibe/domain pair."""

    def test_meta_vibe_returns_live_ops(self) -> None:
        """META vibe triggers live-ops priority list."""
        result = get_collection_priorities("META", "general")
        assert result == ["feature_dna", "lab_infrastructure", "lab_journal"]

    def test_meta_case_insensitive(self) -> None:
        """META vibe matching is case-insensitive."""
        result = get_collection_priorities("meta", "general")
        assert result == ["feature_dna", "lab_infrastructure", "lab_journal"]

    def test_lab_internal_domain_returns_live_ops(self) -> None:
        """lab_internal domain triggers live-ops priority list."""
        result = get_collection_priorities("general", "lab_internal")
        assert result == ["feature_dna", "lab_infrastructure", "lab_journal"]

    def test_meta_and_lab_internal_returns_live_ops(self) -> None:
        """Both META vibe and lab_internal domain return live-ops (not duplicated)."""
        result = get_collection_priorities("META", "lab_internal")
        assert result == ["feature_dna", "lab_infrastructure", "lab_journal"]

    def test_lab_history_returns_historical(self) -> None:
        """lab_history domain returns career_ledger and artifact_vault."""
        result = get_collection_priorities("general", "lab_history")
        assert result == ["career_ledger", "artifact_vault"]

    def test_default_returns_all_collections(self) -> None:
        """Non-specialized vibe/domain returns full default list."""
        result = get_collection_priorities("general", "general")
        assert len(result) == 6
        assert "feature_dna" in result
        assert "career_ledger" in result
        assert "behavioral_dna" in result

    def test_career_ledger_absent_from_live_ops(self) -> None:
        """career_ledger is suppressed in META live-ops routing."""
        result = get_collection_priorities("META", "general")
        assert "career_ledger" not in result

    def test_behavioral_dna_absent_from_live_ops(self) -> None:
        """behavioral_dna is suppressed in META live-ops routing."""
        result = get_collection_priorities("META", "general")
        assert "behavioral_dna" not in result

    def test_returns_list_copy(self) -> None:
        """Each call returns an independent list (no shared mutable state)."""
        a = get_collection_priorities("META", "general")
        b = get_collection_priorities("META", "general")
        assert a == b
        a.append("rogue")
        assert "rogue" not in b


# ═══════════════════════════════════════════════════════════════════════════════
# 2. filter_candidate_context
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilterCandidateContext:
    """Zero Context gate, live-ops suppression, and distance sorting."""

    def _make_candidate(
        self, coll: str, distance: float, doc: str = "doc"
    ) -> dict:
        return {"collection": coll, "distance": distance, "doc": doc}

    def test_empty_candidates_returns_empty(self) -> None:
        """Empty input returns empty list."""
        assert filter_candidate_context([], "general", "general") == []

    def test_zero_context_gate_top_above_threshold(self) -> None:
        """Top candidate distance > max_distance returns empty list."""
        candidates = [
            self._make_candidate("feature_dna", 0.70),
            self._make_candidate("feature_dna", 0.60),
        ]
        result = filter_candidate_context(candidates, "general", "general")
        assert result == []

    def test_zero_context_gate_top_at_threshold(self) -> None:
        """Top candidate distance == max_distance returns results (<= is OK)."""
        candidates = [
            self._make_candidate("feature_dna", 0.50),
            self._make_candidate("feature_dna", 0.30),
        ]
        result = filter_candidate_context(candidates, "general", "general")
        assert len(result) == 2

    def test_zero_context_gate_top_below_threshold(self) -> None:
        """Top candidate distance < max_distance returns results."""
        candidates = [
            self._make_candidate("feature_dna", 0.20),
            self._make_candidate("feature_dna", 0.40),
        ]
        result = filter_candidate_context(candidates, "general", "general")
        assert len(result) == 2

    def test_sorted_by_distance_ascending(self) -> None:
        """Candidates are returned sorted by distance, best first."""
        candidates = [
            self._make_candidate("feature_dna", 0.40, "far"),
            self._make_candidate("feature_dna", 0.10, "near"),
            self._make_candidate("feature_dna", 0.30, "mid"),
        ]
        result = filter_candidate_context(candidates, "general", "general")
        distances = [c["distance"] for c in result]
        assert distances == [0.10, 0.30, 0.40]

    def test_suppresses_career_ledger_for_meta_vibe(self) -> None:
        """career_ledger candidates are removed for META vibe."""
        candidates = [
            self._make_candidate("career_ledger", 0.10),
            self._make_candidate("feature_dna", 0.20),
        ]
        result = filter_candidate_context(candidates, "META", "general")
        assert len(result) == 1
        assert result[0]["collection"] == "feature_dna"

    def test_suppresses_behavioral_dna_for_meta_vibe(self) -> None:
        """behavioral_dna candidates are removed for META vibe."""
        candidates = [
            self._make_candidate("behavioral_dna", 0.10),
            self._make_candidate("feature_dna", 0.20),
        ]
        result = filter_candidate_context(candidates, "META", "general")
        assert len(result) == 1
        assert result[0]["collection"] == "feature_dna"

    def test_suppresses_for_lab_internal_domain(self) -> None:
        """career_ledger and behavioral_dna are suppressed for lab_internal."""
        candidates = [
            self._make_candidate("career_ledger", 0.10),
            self._make_candidate("behavioral_dna", 0.15),
            self._make_candidate("feature_dna", 0.20),
        ]
        result = filter_candidate_context(candidates, "general", "lab_internal")
        assert len(result) == 1
        assert result[0]["collection"] == "feature_dna"

    def test_no_suppression_for_general_context(self) -> None:
        """All collections are kept for non-META, non-lab_internal."""
        candidates = [
            self._make_candidate("career_ledger", 0.10),
            self._make_candidate("behavioral_dna", 0.15),
            self._make_candidate("feature_dna", 0.20),
        ]
        result = filter_candidate_context(candidates, "general", "general")
        assert len(result) == 3

    def test_custom_max_distance(self) -> None:
        """Custom max_distance threshold is respected."""
        candidates = [self._make_candidate("feature_dna", 0.35)]
        # Default 0.50 would pass, but 0.30 rejects
        result = filter_candidate_context(
            candidates, "general", "general", max_distance=0.30
        )
        assert result == []

    def test_all_suppressed_returns_empty(self) -> None:
        """If every candidate is from suppressed collections, result is empty."""
        candidates = [
            self._make_candidate("career_ledger", 0.10),
            self._make_candidate("behavioral_dna", 0.20),
        ]
        result = filter_candidate_context(candidates, "META", "general")
        assert result == []

    def test_missing_distance_defaults_to_1(self) -> None:
        """Candidates missing 'distance' key default to 1.0 (triggers gate)."""
        candidates = [{"collection": "feature_dna", "doc": "no distance key"}]
        result = filter_candidate_context(candidates, "general", "general")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# 3. format_lab_dna_tag
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatLabDnaTag:
    """DNA tag formatting across all collection types."""

    def test_feature_dna_with_id(self) -> None:
        """feature_dna with feature_id produces [FEATURE_DNA: FEAT-469]."""
        result = format_lab_dna_tag(
            "feature_dna", {"feature_id": "FEAT-469"}, "Router implemented"
        )
        assert result == "[FEATURE_DNA: FEAT-469] Router implemented"

    def test_feature_dna_without_id(self) -> None:
        """feature_dna without feature_id produces bare [FEATURE_DNA]."""
        result = format_lab_dna_tag("feature_dna", {}, "Some doc")
        assert result == "[FEATURE_DNA] Some doc"

    def test_lab_infrastructure_with_component(self) -> None:
        """lab_infrastructure with component produces [INFRA: LAB-055]."""
        result = format_lab_dna_tag(
            "lab_infrastructure", {"component": "LAB-055"}, "Sweeper status"
        )
        assert result == "[INFRA: LAB-055] Sweeper status"

    def test_lab_infrastructure_without_component(self) -> None:
        """lab_infrastructure without component produces bare [INFRA]."""
        result = format_lab_dna_tag("lab_infrastructure", {}, "Status")
        assert result == "[INFRA] Status"

    def test_behavioral_dna_with_bkm_id(self) -> None:
        """behavioral_dna with bkm_id produces [BKM: BKM-004]."""
        result = format_lab_dna_tag(
            "behavioral_dna", {"bkm_id": "BKM-004"}, "QQ Protocol"
        )
        assert result == "[BKM: BKM-004] QQ Protocol"

    def test_behavioral_dna_without_bkm_id(self) -> None:
        """behavioral_dna without bkm_id produces bare [BKM]."""
        result = format_lab_dna_tag("behavioral_dna", {}, "Protocol doc")
        assert result == "[BKM] Protocol doc"

    def test_career_ledger_tag(self) -> None:
        """career_ledger produces [CAREER] tag."""
        result = format_lab_dna_tag("career_ledger", {}, "2018 PAE notes")
        assert result == "[CAREER] 2018 PAE notes"

    def test_artifact_vault_tag(self) -> None:
        """artifact_vault produces [ARTIFACT] tag."""
        result = format_lab_dna_tag("artifact_vault", {}, "PDF scan")
        assert result == "[ARTIFACT] PDF scan"

    def test_lab_journal_tag(self) -> None:
        """lab_journal produces [JOURNAL] tag."""
        result = format_lab_dna_tag("lab_journal", {}, "Session log")
        assert result == "[JOURNAL] Session log"

    def test_unknown_collection_returns_raw(self) -> None:
        """Unknown collection returns document text without any tag."""
        result = format_lab_dna_tag("unknown_collection", {}, "Raw text")
        assert result == "Raw text"

    def test_empty_doc_with_tag(self) -> None:
        """Empty document still gets the tag prepended."""
        result = format_lab_dna_tag("feature_dna", {"feature_id": "FEAT-999"}, "")
        assert result == "[FEATURE_DNA: FEAT-999] "
