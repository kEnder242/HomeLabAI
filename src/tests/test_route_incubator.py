"""
[FEAT-472] Unit Tests for Dynamic Route Incubation Sandbox

Covers:
    1. Supplement loading – happy path, missing file, invalid JSON, schema errors
    2. Route registration – prefix, duplicates, traversal modes, persistence
    3. Hit tracking – success/failure counting, feedback, retired routes
    4. Candidate retrieval – active_only filter, all routes
    5. Export for solidification – schema format, metadata, disabled routes
    6. Route retirement – disable, already-retired, re-register
    7. Schema validation – required fields, type checks, traversal modes
    8. Edge cases – empty supplement, concurrent operations, atomic writes
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from src.logic.route_incubator import (
    RouteIncubator,
    RouteIncubatorError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

EMPTY_SUPPLEMENT: dict[str, Any] = {
    "_schema_version": "1.0.0",
    "_description": "Dynamic Route Incubation Sandbox",
    "candidates": {},
}


def _make_candidate(
    intent: str = "test intent",
    target_domain: str = "test_domain",
    enabled: bool = True,
    creator: str = "Brain",
    hit_count: int = 0,
    success_count: int = 0,
    traversal_mode: str | None = None,
    rag_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a candidate route dict for testing."""
    candidate: dict[str, Any] = {
        "intent": intent,
        "target_domain": target_domain,
        "enabled": enabled,
        "creator": creator,
        "created_at": time.time(),
        "hit_count": hit_count,
        "success_count": success_count,
        "last_used": 0.0,
        "feedback_log": [],
    }
    if traversal_mode is not None:
        candidate["traversal_mode"] = traversal_mode
    if rag_config is not None:
        candidate["rag_config"] = rag_config
    return candidate


@pytest.fixture
def supplement_file(tmp_path: Path) -> Path:
    """Write an empty supplement to a temp file and return the path."""
    p = tmp_path / "triage_supplement.json"
    p.write_text(json.dumps(EMPTY_SUPPLEMENT, indent=4), encoding="utf-8")
    return p


@pytest.fixture
def incubator(supplement_file: Path) -> RouteIncubator:
    """Create an incubator pre-loaded with an empty supplement."""
    inc = RouteIncubator(supplement_path=supplement_file)
    inc.load_supplement()
    return inc


@pytest.fixture
def populated_incubator(supplement_file: Path) -> RouteIncubator:
    """Create an incubator with one pre-registered route."""
    inc = RouteIncubator(supplement_path=supplement_file)
    inc.load_supplement()
    inc.register_candidate_route(
        vibe_name="TEST_ROUTE",
        intent="Test route for unit tests",
        target_domain="test_domain",
        traversal_mode="TOPIC_FIRST",
    )
    return inc


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Supplement Loading
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadSupplement:
    """Loading and caching behaviour."""

    def test_load_empty_supplement(self, supplement_file: Path) -> None:
        """Valid JSON file with empty candidates loads without error."""
        inc = RouteIncubator(supplement_path=supplement_file)
        result = inc.load_supplement()
        assert "candidates" in result
        assert len(result["candidates"]) == 0

    def test_load_caches_result(self, supplement_file: Path) -> None:
        """Second load returns the same cached dict."""
        inc = RouteIncubator(supplement_path=supplement_file)
        r1 = inc.load_supplement()
        r2 = inc.load_supplement()
        assert r1 == r2

    def test_load_override_path(self, supplement_file: Path, tmp_path: Path) -> None:
        """Passing a path argument overrides the instance default."""
        other = tmp_path / "other.json"
        other.write_text(
            json.dumps({"_schema_version": "1.0.0", "candidates": {"X": _make_candidate()}}),
            encoding="utf-8",
        )
        inc = RouteIncubator(supplement_path=supplement_file)
        result = inc.load_supplement(path=other)
        assert "X" in result["candidates"]

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Missing file raises RouteIncubatorError."""
        inc = RouteIncubator(supplement_path=tmp_path / "nope.json")
        with pytest.raises(RouteIncubatorError, match="not found"):
            inc.load_supplement()

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """Malformed JSON raises RouteIncubatorError."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json!!!", encoding="utf-8")
        inc = RouteIncubator(supplement_path=bad)
        with pytest.raises(RouteIncubatorError, match="Invalid JSON"):
            inc.load_supplement()

    def test_load_empty_candidates_key_raises(self, tmp_path: Path) -> None:
        """JSON with no 'candidates' key fails validation."""
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"_schema_version": "1.0.0"}), encoding="utf-8")
        inc = RouteIncubator(supplement_path=f)
        with pytest.raises(RouteIncubatorError, match="Schema validation"):
            inc.load_supplement()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Route Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegisterCandidateRoute:
    """Route registration and prefix handling."""

    def test_register_adds_prefix(self, incubator: RouteIncubator) -> None:
        """Route name gets MOUSE_DEF: prefix automatically."""
        name = incubator.register_candidate_route(
            vibe_name="MY_ROUTE",
            intent="Test",
            target_domain="test",
        )
        assert name == "MOUSE_DEF:MY_ROUTE"

    def test_register_preserves_existing_prefix(self, incubator: RouteIncubator) -> None:
        """Route name with MOUSE_DEF: prefix is not double-prefixed."""
        name = incubator.register_candidate_route(
            vibe_name="MOUSE_DEF:ALREADY_PREFIXED",
            intent="Test",
            target_domain="test",
        )
        assert name == "MOUSE_DEF:ALREADY_PREFIXED"

    def test_register_with_traversal_mode(self, incubator: RouteIncubator) -> None:
        """Route with traversal mode stores it correctly."""
        name = incubator.register_candidate_route(
            vibe_name="TOPIC_ROUTE",
            intent="Topic search",
            target_domain="exp_bkm",
            traversal_mode="TOPIC_FIRST",
        )
        routes = incubator.get_candidate_routes()
        assert routes[name]["traversal_mode"] == "TOPIC_FIRST"

    def test_register_with_rag_config(self, incubator: RouteIncubator) -> None:
        """Route with rag_config stores it correctly."""
        rag = {"target_domain": "test", "traversal": "TOPIC_FIRST", "allowed_collections": ["test"], "max_distance": 0.75}
        name = incubator.register_candidate_route(
            vibe_name="RAG_ROUTE",
            intent="RAG test",
            target_domain="test",
            rag_config=rag,
        )
        routes = incubator.get_candidate_routes()
        assert routes[name]["rag_config"] == rag

    def test_register_duplicate_raises(self, populated_incubator: RouteIncubator) -> None:
        """Registering a duplicate route name raises error."""
        with pytest.raises(RouteIncubatorError, match="already exists"):
            populated_incubator.register_candidate_route(
                vibe_name="TEST_ROUTE",
                intent="Duplicate",
                target_domain="test",
            )

    def test_register_invalid_traversal_raises(self, incubator: RouteIncubator) -> None:
        """Invalid traversal mode raises error."""
        with pytest.raises(RouteIncubatorError, match="Invalid traversal_mode"):
            incubator.register_candidate_route(
                vibe_name="BAD_ROUTE",
                intent="Bad",
                target_domain="test",
                traversal_mode="INVALID",
            )

    def test_register_persists_to_disk(self, supplement_file: Path) -> None:
        """Registration writes to the supplement file on disk."""
        inc = RouteIncubator(supplement_path=supplement_file)
        inc.load_supplement()
        inc.register_candidate_route(
            vibe_name="PERSIST_TEST",
            intent="Persistence test",
            target_domain="test",
        )

        # Read the file directly and verify
        raw = json.loads(supplement_file.read_text(encoding="utf-8"))
        assert "MOUSE_DEF:PERSIST_TEST" in raw["candidates"]

    def test_register_initial_counts_zero(self, incubator: RouteIncubator) -> None:
        """New route starts with hit_count=0, success_count=0."""
        name = incubator.register_candidate_route(
            vibe_name="COUNT_TEST",
            intent="Count test",
            target_domain="test",
        )
        routes = incubator.get_candidate_routes()
        assert routes[name]["hit_count"] == 0
        assert routes[name]["success_count"] == 0

    def test_register_sets_creator(self, incubator: RouteIncubator) -> None:
        """Route stores creator correctly."""
        name = incubator.register_candidate_route(
            vibe_name="CREATOR_TEST",
            intent="Creator test",
            target_domain="test",
            creator="Deep Thought",
        )
        routes = incubator.get_candidate_routes()
        assert routes[name]["creator"] == "Deep Thought"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Hit Tracking
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordRouteHit:
    """Hit counting, success tracking, and feedback."""

    def test_hit_increments_count(self, populated_incubator: RouteIncubator) -> None:
        """Each hit increments hit_count."""
        populated_incubator.record_route_hit("MOUSE_DEF:TEST_ROUTE", success=True)
        routes = populated_incubator.get_candidate_routes()
        assert routes["MOUSE_DEF:TEST_ROUTE"]["hit_count"] == 1

    def test_multiple_hits_accumulate(self, populated_incubator: RouteIncubator) -> None:
        """Multiple hits accumulate correctly."""
        populated_incubator.record_route_hit("TEST_ROUTE", success=True)
        populated_incubator.record_route_hit("TEST_ROUTE", success=False)
        populated_incubator.record_route_hit("TEST_ROUTE", success=True)
        routes = populated_incubator.get_candidate_routes()
        assert routes["MOUSE_DEF:TEST_ROUTE"]["hit_count"] == 3
        assert routes["MOUSE_DEF:TEST_ROUTE"]["success_count"] == 2

    def test_success_only_increments_success_count(self, populated_incubator: RouteIncubator) -> None:
        """Failed hits do not increment success_count."""
        populated_incubator.record_route_hit("TEST_ROUTE", success=False)
        routes = populated_incubator.get_candidate_routes()
        assert routes["MOUSE_DEF:TEST_ROUTE"]["success_count"] == 0

    def test_feedback_logged(self, populated_incubator: RouteIncubator) -> None:
        """Feedback string is logged with timestamp."""
        populated_incubator.record_route_hit(
            "TEST_ROUTE", success=True, feedback="Great route!"
        )
        routes = populated_incubator.get_candidate_routes()
        log = routes["MOUSE_DEF:TEST_ROUTE"]["feedback_log"]
        assert len(log) == 1
        assert log[0]["feedback"] == "Great route!"
        assert log[0]["success"] is True

    def test_empty_feedback_not_logged(self, populated_incubator: RouteIncubator) -> None:
        """Empty feedback string does not add to feedback_log."""
        populated_incubator.record_route_hit("TEST_ROUTE", success=True, feedback="")
        routes = populated_incubator.get_candidate_routes()
        assert len(routes["MOUSE_DEF:TEST_ROUTE"]["feedback_log"]) == 0

    def test_hit_on_nonexistent_raises(self, incubator: RouteIncubator) -> None:
        """Hitting a non-existent route raises error."""
        with pytest.raises(RouteIncubatorError, match="not found"):
            incubator.record_route_hit("NONEXISTENT", success=True)

    def test_hit_on_retired_route_raises(self, populated_incubator: RouteIncubator) -> None:
        """Hitting a retired route raises error."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        with pytest.raises(RouteIncubatorError, match="retired"):
            populated_incubator.record_route_hit("TEST_ROUTE", success=True)

    def test_hit_updates_last_used(self, populated_incubator: RouteIncubator) -> None:
        """Hit updates the last_used timestamp."""
        before = time.time()
        populated_incubator.record_route_hit("TEST_ROUTE", success=True)
        after = time.time()
        routes = populated_incubator.get_candidate_routes()
        last_used = routes["MOUSE_DEF:TEST_ROUTE"]["last_used"]
        assert before <= last_used <= after


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Candidate Retrieval
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCandidateRoutes:
    """Retrieval and filtering of candidates."""

    def test_get_active_only(self, populated_incubator: RouteIncubator) -> None:
        """active_only=True returns only enabled routes."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        routes = populated_incubator.get_candidate_routes(active_only=True)
        assert "MOUSE_DEF:TEST_ROUTE" not in routes

    def test_get_all_includes_retired(self, populated_incubator: RouteIncubator) -> None:
        """active_only=False includes retired routes."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        routes = populated_incubator.get_candidate_routes(active_only=False)
        assert "MOUSE_DEF:TEST_ROUTE" in routes

    def test_empty_candidates(self, incubator: RouteIncubator) -> None:
        """Empty supplement returns empty dict."""
        routes = incubator.get_candidate_routes()
        assert routes == {}

    def test_multiple_routes(self, incubator: RouteIncubator) -> None:
        """Multiple routes are all returned."""
        incubator.register_candidate_route("ROUTE_A", "intent A", "domain_a")
        incubator.register_candidate_route("ROUTE_B", "intent B", "domain_b")
        routes = incubator.get_candidate_routes()
        assert len(routes) == 2
        assert "MOUSE_DEF:ROUTE_A" in routes
        assert "MOUSE_DEF:ROUTE_B" in routes


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Export for Solidification
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportForSolidification:
    """Export format and metadata."""

    def test_export_basic_route(self, incubator: RouteIncubator) -> None:
        """Basic route exports with correct schema."""
        incubator.register_candidate_route(
            vibe_name="EXPORT_TEST",
            intent="Export test",
            target_domain="exp_bkm",
            traversal_mode="TOPIC_FIRST",
        )
        export = incubator.export_for_solidification("MOUSE_DEF:EXPORT_TEST")
        assert export["description"] == "Export test"
        assert export["enabled"] is True
        assert export["default_domain"] == "exp_bkm"

    def test_export_includes_rag_from_traversal(self, incubator: RouteIncubator) -> None:
        """Export synthesizes RAG config from traversal_mode."""
        incubator.register_candidate_route(
            vibe_name="RAG_EXPORT",
            intent="RAG export",
            target_domain="exp_for",
            traversal_mode="TIME_FIRST",
        )
        export = incubator.export_for_solidification("RAG_EXPORT")
        assert "rag" in export
        assert export["rag"]["traversal"] == "TIME_FIRST"
        assert export["rag"]["target_domain"] == "exp_for"

    def test_export_uses_explicit_rag_config(self, incubator: RouteIncubator) -> None:
        """Export uses explicit rag_config over synthesized."""
        custom_rag = {"target_domain": "custom", "traversal": "STREAM_REPLAY", "allowed_collections": ["a"], "max_distance": 0.9}
        incubator.register_candidate_route(
            vibe_name="CUSTOM_RAG",
            intent="Custom RAG",
            target_domain="test",
            rag_config=custom_rag,
        )
        export = incubator.export_for_solidification("CUSTOM_RAG")
        assert export["rag"] == custom_rag

    def test_export_conversational_route_no_rag(self, incubator: RouteIncubator) -> None:
        """Route with no traversal or rag_config exports rag=null."""
        incubator.register_candidate_route(
            vibe_name="CONVO",
            intent="Conversational",
            target_domain="standard",
        )
        export = incubator.export_for_solidification("CONVO")
        assert export["rag"] is None

    def test_export_includes_incubation_metadata(self, incubator: RouteIncubator) -> None:
        """Export includes _incubation metadata."""
        incubator.register_candidate_route(
            vibe_name="META_EXPORT",
            intent="Metadata test",
            target_domain="test",
        )
        incubator.record_route_hit("META_EXPORT", success=True)
        export = incubator.export_for_solidification("META_EXPORT")
        assert "_incubation" in export
        assert export["_incubation"]["hit_count"] == 1
        assert export["_incubation"]["source"] == "MOUSE_DEF:META_EXPORT"

    def test_export_nonexistent_raises(self, incubator: RouteIncubator) -> None:
        """Exporting a non-existent route raises error."""
        with pytest.raises(RouteIncubatorError, match="not found"):
            incubator.export_for_solidification("NONEXISTENT")

    def test_export_retired_route_raises(self, populated_incubator: RouteIncubator) -> None:
        """Exporting a retired route raises error."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        with pytest.raises(RouteIncubatorError, match="retired"):
            populated_incubator.export_for_solidification("TEST_ROUTE")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Route Retirement
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetireCandidateRoute:
    """Retirement and lifecycle management."""

    def test_retire_disables_route(self, populated_incubator: RouteIncubator) -> None:
        """Retiring sets enabled=False."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        routes = populated_incubator.get_candidate_routes(active_only=False)
        assert routes["MOUSE_DEF:TEST_ROUTE"]["enabled"] is False

    def test_retire_excluded_from_active(self, populated_incubator: RouteIncubator) -> None:
        """Retired routes excluded from active_only=True."""
        populated_incubator.retire_candidate_route("TEST_ROUTE")
        routes = populated_incubator.get_candidate_routes(active_only=True)
        assert "MOUSE_DEF:TEST_ROUTE" not in routes

    def test_retire_nonexistent_raises(self, incubator: RouteIncubator) -> None:
        """Retiring a non-existent route raises error."""
        with pytest.raises(RouteIncubatorError, match="not found"):
            incubator.retire_candidate_route("NONEXISTENT")

    def test_retire_persists(self, supplement_file: Path) -> None:
        """Retirement is written to disk."""
        inc = RouteIncubator(supplement_path=supplement_file)
        inc.load_supplement()
        inc.register_candidate_route("PERSIST_RETIRE", "test", "test")
        inc.retire_candidate_route("MOUSE_DEF:PERSIST_RETIRE")

        raw = json.loads(supplement_file.read_text(encoding="utf-8"))
        assert raw["candidates"]["MOUSE_DEF:PERSIST_RETIRE"]["enabled"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateSupplementSchema:
    """Direct schema validation tests."""

    def test_valid_empty_passes(self) -> None:
        """Empty candidates dict returns no errors."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        errors = inc.validate_supplement_schema(EMPTY_SUPPLEMENT)
        assert errors == []

    def test_valid_candidate_passes(self) -> None:
        """Full valid candidate returns no errors."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        supplement = {"_schema_version": "1.0.0", "candidates": {"MOUSE_DEF:X": _make_candidate()}}
        errors = inc.validate_supplement_schema(supplement)
        assert errors == []

    def test_root_not_dict(self) -> None:
        """Non-dict root is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        errors = inc.validate_supplement_schema("not a dict")  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "root must be" in errors[0].lower()

    def test_missing_candidates_key(self) -> None:
        """Missing 'candidates' key is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0"})
        assert any("candidates" in e for e in errors)

    def test_candidate_not_dict(self) -> None:
        """A candidate value that isn't a dict is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0", "candidates": {"BAD": "not a dict"}})
        assert any("must be a JSON object" in e for e in errors)

    def test_missing_required_field(self) -> None:
        """Missing 'intent' field is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        candidate = _make_candidate()
        del candidate["intent"]
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0", "candidates": {"X": candidate}})
        assert any("intent" in e for e in errors)

    def test_enabled_not_bool(self) -> None:
        """Non-boolean 'enabled' is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        candidate = _make_candidate(enabled="yes")  # type: ignore[arg-type]
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0", "candidates": {"X": candidate}})
        assert any("boolean" in e for e in errors)

    def test_hit_count_not_int(self) -> None:
        """Non-integer 'hit_count' is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        candidate = _make_candidate(hit_count="five")  # type: ignore[arg-type]
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0", "candidates": {"X": candidate}})
        assert any("hit_count" in e and "integer" in e for e in errors)

    def test_invalid_traversal_mode(self) -> None:
        """Invalid traversal_mode is rejected."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        candidate = _make_candidate(traversal_mode="INVALID")
        errors = inc.validate_supplement_schema({"_schema_version": "1.0.0", "candidates": {"X": candidate}})
        assert any("traversal_mode" in e for e in errors)

    def test_multiple_errors_collected(self) -> None:
        """Multiple schema violations produce multiple error strings."""
        inc = RouteIncubator(supplement_path="/tmp/fake.json")
        errors = inc.validate_supplement_schema({
            "_schema_version": "1.0.0",
            "candidates": {
                "A": {"enabled": True},  # missing intent, target_domain, etc.
                "B": {"intent": "b", "target_domain": "d", "enabled": "no", "creator": "c", "created_at": 0, "hit_count": -1, "success_count": 0, "last_used": 0, "feedback_log": []},
            },
        })
        assert len(errors) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Edge Cases & Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_name_resolution_without_prefix(self, incubator: RouteIncubator) -> None:
        """Name resolution adds prefix when missing."""
        incubator.register_candidate_route("SHORT", "test", "test")
        assert "MOUSE_DEF:SHORT" in incubator.get_candidate_routes()

    def test_name_resolution_with_prefix(self, incubator: RouteIncubator) -> None:
        """Name resolution preserves existing prefix."""
        incubator.register_candidate_route("MOUSE_DEF:LONG", "test", "test")
        assert "MOUSE_DEF:LONG" in incubator.get_candidate_routes()

    def test_all_traversal_modes_valid(self, incubator: RouteIncubator) -> None:
        """All three traversal modes can be registered."""
        for mode in ("TOPIC_FIRST", "TIME_FIRST", "STREAM_REPLAY"):
            incubator.register_candidate_route(
                f"MODE_{mode}", "test", "test", traversal_mode=mode
            )
        routes = incubator.get_candidate_routes()
        assert len(routes) == 3

    def test_export_without_traversal_has_null_rag(self, incubator: RouteIncubator) -> None:
        """Route with no traversal and no rag_config exports rag=null."""
        incubator.register_candidate_route("NO_TRAV", "test", "standard")
        export = incubator.export_for_solidification("NO_TRAV")
        assert export["rag"] is None

    def test_incubator_default_path(self) -> None:
        """Default path is config/triage_supplement.json."""
        inc = RouteIncubator()
        assert str(inc._supplement_path).endswith("triage_supplement.json")

    def test_persistence_creates_file(self, tmp_path: Path) -> None:
        """Persist writes the supplement file even if it doesn't exist yet."""
        new_file = tmp_path / "new_supplement.json"
        inc = RouteIncubator(supplement_path=new_file)
        # Manually initialize candidates and persist
        inc._candidates = {}
        inc._persist()
        assert new_file.exists()
        raw = json.loads(new_file.read_text(encoding="utf-8"))
        assert raw["candidates"] == {}
