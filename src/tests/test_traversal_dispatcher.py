"""
[FEAT-117/467] Tests for Bidirectional Traversal Dispatcher

Tests:
    1. TOPIC_FIRST mode - keyword prioritization and collection routing
    2. TIME_FIRST mode - temporal anchor extraction and bounds
    3. STREAM_REPLAY mode - short-term stream targeting
    4. format_traversal_query - main entry point
    5. resolve_collection_scope - vibe/domain/mode collection routing
    6. Helper functions - extract_temporal_anchors
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.logic.traversal_dispatcher import (
    TraversalMode,
    format_traversal_query,
    resolve_collection_scope,
    extract_temporal_anchors,
    get_temporal_bounds,
    is_temporal_query,
)


# ─── TOPIC_FIRST Mode Tests ─────────────────────────────────────────────────

class TestTopicFirstMode:
    """Test TOPIC_FIRST traversal mode - keyword prioritization and routing."""

    def test_basic_topic_first_query(self):
        """Verify basic TOPIC_FIRST produces artifact_vault + behavioral_dna."""
        result = format_traversal_query("silicon validation", "TOPIC_FIRST")
        assert result["mode"] == "TOPIC_FIRST"
        assert "artifact_vault" in result["collections"]
        assert "behavioral_dna" in result["collections"]
        assert result["temporal_bounds"] is None

    def test_topic_first_keyword_prioritization(self):
        """Verify silicon keywords get higher priority than career keywords."""
        result = format_traversal_query("silicon telemetry career", "TOPIC_FIRST")
        terms = result["enriched_terms"]
        # silicon should appear before career
        silicon_idx = next((i for i, t in enumerate(terms) if "silicon" in t.lower()), -1)
        career_idx = next((i for i, t in enumerate(terms) if "career" in t.lower()), -1)
        if silicon_idx >= 0 and career_idx >= 0:
            assert silicon_idx < career_idx

    def test_topic_first_protocol_keywords(self):
        """Verify protocol/BKM keywords are recognized."""
        result = format_traversal_query("BKM-034 protocol", "TOPIC_FIRST")
        terms = result["enriched_terms"]
        assert any("bkm" in t.lower() or "protocol" in t.lower() for t in terms)

    def test_topic_first_boost_flags(self):
        """Verify boost flags are set for artifact_vault and behavioral_dna."""
        result = format_traversal_query("code implementation", "TOPIC_FIRST")
        assert result["boost_artifact_vault"] is True
        assert result["boost_behavioral_dna"] is True

    def test_topic_first_with_metadata_domain(self):
        """Verify metadata domain is prepended to enriched terms."""
        result = format_traversal_query(
            "validation", "TOPIC_FIRST", metadata={"domain": "exp_tlm"}
        )
        assert result["enriched_terms"][0] == "exp_tlm"


# ─── TIME_FIRST Mode Tests ──────────────────────────────────────────────────

class TestTimeFirstMode:
    """Test TIME_FIRST traversal mode - temporal anchor extraction."""

    def test_basic_time_first_with_year(self):
        """Verify TIME_FIRST with year anchor sets temporal bounds."""
        result = format_traversal_query("work in 2018", "TIME_FIRST")
        assert result["mode"] == "TIME_FIRST"
        assert result["temporal_bounds"] is not None
        assert result["temporal_bounds"]["type"] == "year_range"
        assert result["temporal_bounds"]["start_year"] == 2018

    def test_time_first_year_range(self):
        """Verify multiple years create a range."""
        result = format_traversal_query("from 2015 to 2020", "TIME_FIRST")
        bounds = result["temporal_bounds"]
        assert bounds["start_year"] == 2015
        assert bounds["end_year"] == 2020

    def test_time_first_sprint_anchor(self):
        """Verify Sprint N anchors are extracted."""
        result = format_traversal_query("Sprint 35 changes", "TIME_FIRST")
        bounds = result["temporal_bounds"]
        assert bounds["type"] == "sprint_range"
        assert 35 in bounds["sprints"]

    def test_time_first_era_marker(self):
        """Verify era markers like 'early career' are extracted."""
        result = format_traversal_query("early career experiences", "TIME_FIRST")
        bounds = result["temporal_bounds"]
        assert bounds["type"] == "era"
        assert any("early" in e for e in bounds["eras"])

    def test_time_first_collections(self):
        """Verify TIME_FIRST targets career_ledger and artifact_vault."""
        result = format_traversal_query("2024 projects", "TIME_FIRST")
        assert "career_ledger" in result["collections"]
        assert "artifact_vault" in result["collections"]
        assert result["boost_career_ledger"] is True


# ─── STREAM_REPLAY Mode Tests ────────────────────────────────────────────────

class TestStreamReplayMode:
    """Test STREAM_REPLAY mode - short-term stream targeting."""

    def test_stream_replay_targets_short_term(self):
        """Verify STREAM_REPLAY only targets short_term_stream."""
        result = format_traversal_query("recent conversation", "STREAM_REPLAY")
        assert result["mode"] == "STREAM_REPLAY"
        assert result["collections"] == ["short_term_stream"]
        assert result["exclude_career_notes"] is True

    def test_stream_replay_session_limit(self):
        """Verify session_limit defaults to 10."""
        result = format_traversal_query("recent chat", "STREAM_REPLAY")
        assert result["session_limit"] == 10

    def test_stream_replay_custom_session_limit(self):
        """Verify session_limit can be overridden via metadata."""
        result = format_traversal_query(
            "recent chat", "STREAM_REPLAY", metadata={"session_limit": 20}
        )
        assert result["session_limit"] == 20


# ─── format_traversal_query Entry Point Tests ───────────────────────────────

class TestFormatTraversalQuery:
    """Test the main format_traversal_query entry point."""

    def test_invalid_mode_raises_value_error(self):
        """Verify invalid traversal mode raises ValueError."""
        try:
            format_traversal_query("test", "INVALID_MODE")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid traversal mode" in str(e)

    def test_enum_mode_works(self):
        """Verify passing TraversalMode enum directly works."""
        result = format_traversal_query("test", TraversalMode.TOPIC_FIRST)
        assert result["mode"] == "TOPIC_FIRST"

    def test_empty_query_returns_empty(self):
        """Verify empty query returns minimal result."""
        result = format_traversal_query("", "TOPIC_FIRST")
        assert result["query_text"] == ""
        assert result["enriched_terms"] == []

    def test_whitespace_query_returns_empty(self):
        """Verify whitespace-only query returns minimal result."""
        result = format_traversal_query("   ", "TOPIC_FIRST")
        assert result["query_text"] == "   "  # Original preserved
        assert result["enriched_terms"] == []  # No enriched terms for empty

    def test_none_metadata_handled(self):
        """Verify None metadata doesn't cause errors."""
        result = format_traversal_query("test", "TOPIC_FIRST", metadata=None)
        assert result is not None

    def test_temporal_bounds_override(self):
        """Verify metadata temporal_bounds overrides extraction."""
        custom_bounds = {"type": "year_range", "start_year": 2000, "end_year": 2025}
        result = format_traversal_query(
            "2018 work", "TIME_FIRST", metadata={"temporal_bounds": custom_bounds}
        )
        assert result["temporal_bounds"] == custom_bounds


# ─── resolve_collection_scope Tests ─────────────────────────────────────────

class TestResolveCollectionScope:
    """Test collection scope resolution based on vibe/domain/mode."""

    def test_casual_vibe_returns_short_term(self):
        """Verify CASUAL vibe always returns short_term_stream."""
        collections = resolve_collection_scope("CASUAL", None, "TOPIC_FIRST")
        assert collections == ["short_term_stream"]

    def test_supervisory_vibe_returns_short_term(self):
        """Verify SUPERVISORY vibe always returns short_term_stream."""
        collections = resolve_collection_scope("SUPERVISORY", None, "TIME_FIRST")
        assert collections == ["short_term_stream"]

    def test_meta_vibe_returns_short_term(self):
        """Verify META vibe always returns short_term_stream."""
        collections = resolve_collection_scope("META", None, "TOPIC_FIRST")
        assert collections == ["short_term_stream"]

    def test_stream_replay_mode_returns_short_term(self):
        """Verify STREAM_REPLAY mode always returns short_term_stream."""
        collections = resolve_collection_scope("TECHNICAL", None, "STREAM_REPLAY")
        assert collections == ["short_term_stream"]

    def test_historical_vibe_boosts_career_ledger(self):
        """Verify HISTORICAL vibe adds career_ledger."""
        collections = resolve_collection_scope("HISTORICAL", None, "TOPIC_FIRST")
        assert "career_ledger" in collections

    def test_technical_vibe_boosts_behavioral_dna(self):
        """Verify TECHNICAL vibe adds behavioral_dna."""
        collections = resolve_collection_scope("TECHNICAL", None, "TOPIC_FIRST")
        assert "behavioral_dna" in collections

    def test_domain_exp_tlm_adds_artifact_vault(self):
        """Verify exp_tlm domain adds artifact_vault."""
        collections = resolve_collection_scope("TECHNICAL", "exp_tlm", "TOPIC_FIRST")
        assert "artifact_vault" in collections

    def test_domain_exp_bkm_adds_behavioral_dna(self):
        """Verify exp_bkm domain adds behavioral_dna."""
        collections = resolve_collection_scope("TECHNICAL", "exp_bkm", "TOPIC_FIRST")
        assert "behavioral_dna" in collections

    def test_domain_lab_history_adds_career_ledger(self):
        """Verify lab_history domain adds career_ledger."""
        collections = resolve_collection_scope("TECHNICAL", "lab_history", "TOPIC_FIRST")
        assert "career_ledger" in collections

    def test_no_duplicates_in_collections(self):
        """Verify collection list has no duplicates."""
        collections = resolve_collection_scope("TECHNICAL", "exp_tlm", "TOPIC_FIRST")
        assert len(collections) == len(set(collections))

    def test_invalid_mode_falls_back_to_topic_first(self):
        """Verify invalid mode falls back to TOPIC_FIRST collections."""
        collections = resolve_collection_scope("TECHNICAL", None, "INVALID")
        # Should still return some collections (TOPIC_FIRST fallback)
        assert len(collections) > 0


# ─── Helper Function Tests ──────────────────────────────────────────────────

class TestExtractTemporalAnchors:
    """Test temporal anchor extraction helper."""

    def test_extracts_single_year(self):
        """Verify single year extraction."""
        result = extract_temporal_anchors("work in 2018")
        assert result["years"] == [2018]
        assert result["has_temporal"] is True

    def test_extracts_multiple_years(self):
        """Verify multiple year extraction."""
        result = extract_temporal_anchors("from 2015 to 2020")
        assert 2015 in result["years"]
        assert 2020 in result["years"]

    def test_extracts_sprint_number(self):
        """Verify Sprint N extraction."""
        result = extract_temporal_anchors("Sprint 35")
        assert 35 in result["sprints"]
        assert result["has_temporal"] is True

    def test_extracts_era_markers(self):
        """Verify era marker extraction."""
        result = extract_temporal_anchors("early career")
        assert len(result["eras"]) > 0
        assert "early" in result["eras"][0]

    def test_no_temporal_anchors(self):
        """Verify empty result for query with no temporal anchors."""
        result = extract_temporal_anchors("silicon validation")
        assert result["has_temporal"] is False
        assert result["years"] == []
        assert result["sprints"] == []


# ─── Convenience Function Tests ─────────────────────────────────────────────

class TestConvenienceFunctions:
    """Test get_temporal_bounds, is_temporal_query."""

    def test_get_temporal_bounds_with_year(self):
        """Verify get_temporal_bounds returns bounds for year query."""
        bounds = get_temporal_bounds("work in 2018")
        assert bounds is not None
        assert bounds["start_year"] == 2018

    def test_get_temporal_bounds_none_for_no_temporal(self):
        """Verify get_temporal_bounds returns None for non-temporal query."""
        bounds = get_temporal_bounds("silicon validation")
        assert bounds is None

    def test_is_temporal_query_true(self):
        """Verify is_temporal_query returns True for temporal queries."""
        assert is_temporal_query("2018 projects") is True
        assert is_temporal_query("Sprint 35") is True
        assert is_temporal_query("early career") is True

    def test_is_temporal_query_false(self):
        """Verify is_temporal_query returns False for non-temporal queries."""
        assert is_temporal_query("silicon validation") is False
        assert is_temporal_query("BKM-034 protocol") is False
