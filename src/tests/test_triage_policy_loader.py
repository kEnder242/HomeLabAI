"""
[FEAT-467] Unit Tests for Declarative Triage Policy Loader

Covers:
    1. Policy loading - happy path, missing file, invalid JSON, schema errors
    2. Vibe rule lookup - exact, case-insensitive, missing
    3. Active vibes - filtering, empty policy
    4. Schema validation - required fields, RAG validation, edge cases
    5. Hot reload - mtime detection, missing file, parse failure
    6. RAG config - present, absent, partial, malformed
    7. Production config grounding - WYWO definition, CASUAL importance
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from src.logic.triage_policy_loader import (
    TriagePolicyError,
    TriagePolicyLoader,
)


# ===========================================================================
# Fixtures
# ===========================================================================

VALID_POLICY: dict[str, Any] = {
    "_schema_version": "1.0.0",
    "vibes": {
        "CASUAL": {
            "description": "Colloquial greetings and pleasantries",
            "enabled": True,
            "default_domain": "standard",
            "rag": None,
            "importance": 0.1,
            "examples": ["how are things?", "hello", "good morning"],
        },
        "SUPERVISORY": {
            "description": "Supervisory feedback loop",
            "enabled": True,
            "default_domain": "standard",
        },
        "WYWO": {
            "description": "'While You Were Out' Standup Briefing",
            "enabled": True,
            "default_domain": "dream_stream",
            "rag": {
                "target_domain": "dream_stream",
                "traversal": "STREAM_REPLAY",
                "allowed_collections": ["dream_cache", "stream_log"],
                "max_distance": 0.85,
            },
        },
        "META": {
            "description": "Lab-internal meta queries",
            "enabled": True,
            "default_domain": "lab_internal",
        },
        "OPERATIONAL": {
            "description": "SRE diagnostics",
            "enabled": True,
            "default_domain": "exp_bkm",
            "rag": {
                "target_domain": "exp_bkm",
                "traversal": "TOPIC_FIRST",
                "allowed_collections": ["behavioral_dna", "artifact_vault"],
                "max_distance": 0.75,
            },
        },
        "FORENSIC": {
            "description": "Forensic log analysis",
            "enabled": True,
            "default_domain": "exp_for",
            "rag": {
                "target_domain": "exp_for",
                "traversal": "TIME_FIRST",
                "allowed_collections": ["career_ledger", "artifact_vault"],
                "max_distance": 0.70,
            },
        },
        "TECHNICAL": {
            "description": "Technical deep-dive",
            "enabled": True,
            "default_domain": "exp_tlm",
            "rag": {
                "target_domain": "exp_tlm",
                "traversal": "TOPIC_FIRST",
                "allowed_collections": ["behavioral_dna", "artifact_vault", "career_ledger"],
                "max_distance": 0.70,
            },
        },
        "HISTORICAL": {
            "description": "18-year career archive",
            "enabled": True,
            "default_domain": "lab_history",
            "rag": {
                "target_domain": "lab_history",
                "traversal": "TIME_FIRST",
                "allowed_collections": ["career_ledger", "long_term_wisdom"],
                "max_distance": 0.80,
            },
        },
    },
}


@pytest.fixture
def tmp_policy_file(tmp_path: Path) -> Path:
    """Write a valid policy to a temp file and return the path."""
    p = tmp_path / "triage_policy.json"
    p.write_text(json.dumps(VALID_POLICY, indent=4), encoding="utf-8")
    return p


@pytest.fixture
def loader(tmp_policy_file: Path) -> TriagePolicyLoader:
    """Create a loader pre-loaded with a valid policy."""
    ld = TriagePolicyLoader(policy_path=tmp_policy_file)
    ld.load_policy()
    return ld


# ===========================================================================
# 1. Policy Loading
# ===========================================================================


class TestLoadPolicy:
    """Loading and caching behaviour."""

    def test_load_valid_policy(self, tmp_policy_file: Path) -> None:
        """Valid JSON file loads without error."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        policy = ld.load_policy()
        assert "vibes" in policy
        assert len(policy["vibes"]) == 8

    def test_load_caches_result(self, tmp_policy_file: Path) -> None:
        """Second load returns the same cached dict."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        p1 = ld.load_policy()
        p2 = ld.load_policy()
        assert p1 == p2

    def test_load_override_path(self, tmp_policy_file: Path, tmp_path: Path) -> None:
        """Passing a path argument overrides the instance default."""
        other = tmp_path / "other.json"
        other.write_text(json.dumps({"vibes": {"X": {"description": "x", "enabled": False, "default_domain": "std"}}}), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        policy = ld.load_policy(path=other)
        assert "X" in policy["vibes"]

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Missing file raises TriagePolicyError."""
        ld = TriagePolicyLoader(policy_path=tmp_path / "nope.json")
        with pytest.raises(TriagePolicyError, match="not found"):
            ld.load_policy()

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """Malformed JSON raises TriagePolicyError."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json!!!", encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=bad)
        with pytest.raises(TriagePolicyError, match="Invalid JSON"):
            ld.load_policy()

    def test_load_empty_vibes_raises(self, tmp_path: Path) -> None:
        """JSON with no 'vibes' key fails validation."""
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"_schema_version": "1.0.0"}), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        with pytest.raises(TriagePolicyError, match="Schema validation"):
            ld.load_policy()

    def test_load_policy_does_not_cache_on_error(self, tmp_path: Path) -> None:
        """A failed load does not overwrite a previously cached good policy."""
        good = tmp_path / "good.json"
        good.write_text(json.dumps(VALID_POLICY), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=good)
        ld.load_policy()
        original = ld._policy

        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"vibes": {"BROKEN": "not a dict"}}), encoding="utf-8")
        with pytest.raises(TriagePolicyError):
            ld.load_policy(path=bad)

        assert ld._policy is original


# ===========================================================================
# 2. Vibe Rule Lookup
# ===========================================================================


class TestGetVibeRule:
    """Vibe lookup and case handling."""

    def test_get_existing_vibe(self, loader: TriagePolicyLoader) -> None:
        """Known vibe returns its rule dict."""
        rule = loader.get_vibe_rule("FORENSIC")
        assert rule is not None
        assert rule["default_domain"] == "exp_for"

    def test_get_vibe_case_insensitive(self, loader: TriagePolicyLoader) -> None:
        """Lowercase input matches uppercase key."""
        rule = loader.get_vibe_rule("forensic")
        assert rule is not None

    def test_get_vibe_mixed_case(self, loader: TriagePolicyLoader) -> None:
        """Mixed case input matches uppercase key."""
        rule = loader.get_vibe_rule("WyWo")
        assert rule is not None

    def test_get_missing_vibe(self, loader: TriagePolicyLoader) -> None:
        """Unknown vibe returns None."""
        assert loader.get_vibe_rule("NONEXISTENT") is None

    def test_get_vibe_before_load(self) -> None:
        """Lookup before load_policy returns None."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        assert ld.get_vibe_rule("CASUAL") is None


# ===========================================================================
# 3. Active Vibes
# ===========================================================================


class TestGetActiveVibes:
    """Filtering enabled vibes."""

    def test_all_enabled(self, loader: TriagePolicyLoader) -> None:
        """All 8 standard vibes are enabled in the test policy."""
        active = loader.get_active_vibes()
        assert len(active) == 8
        assert "CASUAL" in active
        assert "HISTORICAL" in active

    def test_sorted_output(self, loader: TriagePolicyLoader) -> None:
        """Active vibes are returned in sorted order."""
        active = loader.get_active_vibes()
        assert active == sorted(active)

    def test_disabled_vibe_excluded(self, tmp_path: Path) -> None:
        """A vibe with 'enabled: false' is excluded."""
        policy = dict(VALID_POLICY)
        policy["vibes"] = dict(policy["vibes"])
        policy["vibes"]["CASUAL"] = {**policy["vibes"]["CASUAL"], "enabled": False}
        f = tmp_path / "p.json"
        f.write_text(json.dumps(policy), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        ld.load_policy()
        assert "CASUAL" not in ld.get_active_vibes()
        assert len(ld.get_active_vibes()) == 7

    def test_empty_vibes_returns_empty(self, tmp_path: Path) -> None:
        """An empty vibes dict returns empty list."""
        f = tmp_path / "p.json"
        f.write_text(json.dumps({"vibes": {}}), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        ld.load_policy()
        assert ld.get_active_vibes() == []

    def test_active_vibes_before_load(self) -> None:
        """Calling before load returns empty list."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        assert ld.get_active_vibes() == []


# ===========================================================================
# 4. Schema Validation
# ===========================================================================


class TestValidatePolicySchema:
    """Direct schema validation tests."""

    def test_valid_policy_passes(self) -> None:
        """Full valid policy returns no errors."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        errors = ld.validate_policy_schema(VALID_POLICY)
        assert errors == []

    def test_root_not_dict(self) -> None:
        """Non-dict root is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        errors = ld.validate_policy_schema("not a dict")  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "root must be" in errors[0].lower()

    def test_missing_vibes_key(self) -> None:
        """Missing 'vibes' key is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        errors = ld.validate_policy_schema({"_schema_version": "1.0.0"})
        assert any("vibes" in e for e in errors)

    def test_vibe_not_dict(self) -> None:
        """A vibe value that isn't a dict is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {"vibes": {"BAD": "not a dict"}}
        errors = ld.validate_policy_schema(policy)
        assert any("must be a JSON object" in e for e in errors)

    def test_missing_required_field(self) -> None:
        """Missing 'description' field is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {"vibes": {"X": {"enabled": True, "default_domain": "std"}}}
        errors = ld.validate_policy_schema(policy)
        assert any("description" in e for e in errors)

    def test_enabled_not_bool(self) -> None:
        """Non-boolean 'enabled' is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {"vibes": {"X": {"description": "x", "enabled": "yes", "default_domain": "std"}}}
        errors = ld.validate_policy_schema(policy)
        assert any("boolean" in e for e in errors)

    def test_rag_not_dict(self) -> None:
        """Non-dict 'rag' value is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": "invalid",
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert any("rag" in e and "JSON object" in e for e in errors)

    def test_rag_null_valid(self) -> None:
        """Null 'rag' is accepted (conversational vibes)."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": None,
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert errors == []

    def test_rag_invalid_traversal(self) -> None:
        """Invalid traversal mode is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": {
                        "target_domain": "test",
                        "traversal": "INVALID_MODE",
                    },
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert any("traversal" in e for e in errors)

    def test_rag_allowed_collections_not_list(self) -> None:
        """Non-list 'allowed_collections' is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": {
                        "allowed_collections": "not_a_list",
                    },
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert any("allowed_collections" in e and "list" in e for e in errors)

    def test_rag_max_distance_out_of_range(self) -> None:
        """max_distance outside [0.0, 1.0] is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": {"max_distance": 1.5},
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert any("max_distance" in e and "1.0" in e for e in errors)

    def test_rag_max_distance_not_numeric(self) -> None:
        """Non-numeric max_distance is rejected."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "X": {
                    "description": "x",
                    "enabled": True,
                    "default_domain": "std",
                    "rag": {"max_distance": "far"},
                }
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert any("numeric" in e for e in errors)

    def test_multiple_errors_collected(self) -> None:
        """Multiple schema violations produce multiple error strings."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        policy = {
            "vibes": {
                "A": {"enabled": True},  # missing description, default_domain
                "B": {"description": "b", "enabled": "no", "default_domain": "x"},
            }
        }
        errors = ld.validate_policy_schema(policy)
        assert len(errors) >= 3


# ===========================================================================
# 5. Hot Reload
# ===========================================================================


class TestHotReload:
    """Mtime-based hot-reload detection."""

    def test_no_reload_without_change(self, tmp_policy_file: Path) -> None:
        """Unchanged file does not trigger reload."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        ld.load_policy()
        assert ld.hot_reload_if_modified() is False

    def test_reload_on_mtime_change(self, tmp_policy_file: Path) -> None:
        """Touching the file triggers a reload."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        ld.load_policy()

        # Mutate the file to change mtime
        time.sleep(0.05)
        policy_copy = dict(VALID_POLICY)
        policy_copy["vibes"] = dict(policy_copy["vibes"])
        policy_copy["vibes"]["NEW_VIBE"] = {
            "description": "new",
            "enabled": True,
            "default_domain": "test",
        }
        tmp_policy_file.write_text(json.dumps(policy_copy), encoding="utf-8")

        reloaded = ld.hot_reload_if_modified()
        assert reloaded is True
        assert ld.get_vibe_rule("NEW_VIBE") is not None

    def test_reload_preserves_disabled_vibes(self, tmp_policy_file: Path) -> None:
        """Hot-reload picks up newly disabled vibes."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        ld.load_policy()
        assert "CASUAL" in ld.get_active_vibes()

        time.sleep(0.05)
        policy_copy = dict(VALID_POLICY)
        policy_copy["vibes"] = dict(policy_copy["vibes"])
        policy_copy["vibes"]["CASUAL"] = {**policy_copy["vibes"]["CASUAL"], "enabled": False}
        tmp_policy_file.write_text(json.dumps(policy_copy), encoding="utf-8")

        ld.hot_reload_if_modified()
        assert "CASUAL" not in ld.get_active_vibes()

    def test_hot_reload_skips_on_missing_file(self, tmp_policy_file: Path) -> None:
        """Disappearing file does not crash; returns False."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        ld.load_policy()
        os.unlink(tmp_policy_file)
        assert ld.hot_reload_if_modified() is False

    def test_hot_reload_before_load(self) -> None:
        """hot_reload_if_modified returns False if never loaded."""
        ld = TriagePolicyLoader(policy_path="/tmp/fake.json")
        assert ld.hot_reload_if_modified() is False

    def test_hot_reload_on_invalid_update_keeps_old(self, tmp_policy_file: Path) -> None:
        """Writing invalid JSON keeps the old cached policy."""
        ld = TriagePolicyLoader(policy_path=tmp_policy_file)
        ld.load_policy()
        original = ld._policy

        time.sleep(0.05)
        tmp_policy_file.write_text("NOT JSON!!!", encoding="utf-8")
        reloaded = ld.hot_reload_if_modified()
        assert reloaded is False
        assert ld._policy is original


# ===========================================================================
# 6. RAG Configuration
# ===========================================================================


class TestGetRagConfig:
    """RAG config retrieval and optionality."""

    def test_retrieval_vibe_has_rag(self, loader: TriagePolicyLoader) -> None:
        """TECHNICAL vibe returns a full RAG dict."""
        rag = loader.get_rag_config("TECHNICAL")
        assert rag is not None
        assert rag["traversal"] == "TOPIC_FIRST"
        assert "behavioral_dna" in rag["allowed_collections"]

    def test_conversational_vibe_no_rag(self, loader: TriagePolicyLoader) -> None:
        """CASUAL vibe returns None for RAG."""
        assert loader.get_rag_config("CASUAL") is None

    def test_supervisory_vibe_no_rag(self, loader: TriagePolicyLoader) -> None:
        """SUPERVISORY vibe returns None for RAG."""
        assert loader.get_rag_config("SUPERVISORY") is None

    def test_meta_vibe_no_rag(self, loader: TriagePolicyLoader) -> None:
        """META vibe returns None for RAG."""
        assert loader.get_rag_config("META") is None

    def test_missing_vibe_returns_none(self, loader: TriagePolicyLoader) -> None:
        """Unknown vibe returns None."""
        assert loader.get_rag_config("UNKNOWN") is None

    def test_wywo_stream_replay(self, loader: TriagePolicyLoader) -> None:
        """WYWO uses STREAM_REPLAY traversal."""
        rag = loader.get_rag_config("WYWO")
        assert rag is not None
        assert rag["traversal"] == "STREAM_REPLAY"
        assert rag["target_domain"] == "dream_stream"

    def test_historical_time_first(self, loader: TriagePolicyLoader) -> None:
        """HISTORICAL uses TIME_FIRST traversal."""
        rag = loader.get_rag_config("HISTORICAL")
        assert rag is not None
        assert rag["traversal"] == "TIME_FIRST"
        assert rag["max_distance"] == 0.80

    def test_forensic_rag_collections(self, loader: TriagePolicyLoader) -> None:
        """FORENSIC RAG targets career_ledger and artifact_vault."""
        rag = loader.get_rag_config("FORENSIC")
        assert rag is not None
        assert "career_ledger" in rag["allowed_collections"]
        assert "artifact_vault" in rag["allowed_collections"]


# ===========================================================================
# 7. Production Config Grounding
# ===========================================================================


class TestProductionConfig:
    """Validate the actual config/triage_policy.json shipped with the project."""

    @pytest.fixture(autouse=True)
    def _load_production(self) -> None:
        """Attempt to load the production config; skip if not present."""
        prod_path = Path("config/triage_policy.json")
        if not prod_path.exists():
            pytest.skip("Production triage_policy.json not found")
        self._prod_loader = TriagePolicyLoader(policy_path=prod_path)
        self._prod_loader.load_policy()

    def test_production_has_all_eight_vibes(self) -> None:
        """Production config defines all 8 standard vibes."""
        active = self._prod_loader.get_active_vibes()
        expected = {"CASUAL", "SUPERVISORY", "WYWO", "META", "OPERATIONAL", "FORENSIC", "TECHNICAL", "HISTORICAL"}
        assert set(active) == expected

    def test_production_conversational_no_rag(self) -> None:
        """CASUAL, SUPERVISORY, META have no RAG config."""
        for vibe in ("CASUAL", "SUPERVISORY", "META"):
            assert self._prod_loader.get_rag_config(vibe) is None

    def test_production_retrieval_vibes_have_rag(self) -> None:
        """WYWO, OPERATIONAL, FORENSIC, TECHNICAL, HISTORICAL have RAG."""
        for vibe in ("WYWO", "OPERATIONAL", "FORENSIC", "TECHNICAL", "HISTORICAL"):
            rag = self._prod_loader.get_rag_config(vibe)
            assert rag is not None, f"{vibe} missing RAG config"

    def test_production_traversal_modes_valid(self) -> None:
        """All traversal modes are valid enum values."""
        for vibe in self._prod_loader.get_active_vibes():
            rag = self._prod_loader.get_rag_config(vibe)
            if rag and "traversal" in rag:
                assert rag["traversal"] in {"TOPIC_FIRST", "TIME_FIRST", "STREAM_REPLAY"}

    def test_production_wywo_is_standup_briefing(self) -> None:
        """WYWO description is grounded as 'While You Were Out' Standup Briefing."""
        rule = self._prod_loader.get_vibe_rule("WYWO")
        assert rule is not None
        desc = rule["description"].lower()
        assert "while you were out" in desc or "standup" in desc or "briefing" in desc

    def test_production_casual_has_importance(self) -> None:
        """CASUAL vibe includes importance field for fast-path classification."""
        rule = self._prod_loader.get_vibe_rule("CASUAL")
        assert rule is not None
        assert "importance" in rule
        assert rule["importance"] == 0.1

    def test_production_casual_has_examples(self) -> None:
        """CASUAL vibe includes examples of genuine greeting queries."""
        rule = self._prod_loader.get_vibe_rule("CASUAL")
        assert rule is not None
        assert "examples" in rule
        examples = rule["examples"]
        assert isinstance(examples, list)
        assert len(examples) >= 3
        # Verify at least one genuine greeting example
        examples_lower = [e.lower() for e in examples]
        assert any("how are" in e for e in examples_lower), "CASUAL examples should include greeting patterns"

    def test_production_technical_silicon_grounding(self) -> None:
        """TECHNICAL description mentions silicon telemetry domain."""
        rule = self._prod_loader.get_vibe_rule("TECHNICAL")
        assert rule is not None
        desc = rule["description"].lower()
        assert "silicon" in desc or "telemetry" in desc or "pcie" in desc

    def test_production_forensic_log_grounding(self) -> None:
        """FORENSIC description mentions log analysis domain."""
        rule = self._prod_loader.get_vibe_rule("FORENSIC")
        assert rule is not None
        desc = rule["description"].lower()
        assert "log" in desc or "crash" in desc or "forensic" in desc

    def test_production_operational_sre_grounding(self) -> None:
        """OPERATIONAL description mentions SRE/BKM domain."""
        rule = self._prod_loader.get_vibe_rule("OPERATIONAL")
        assert rule is not None
        desc = rule["description"].lower()
        assert "sre" in desc or "bkm" in desc or "diagnostic" in desc or "playbook" in desc


# ===========================================================================
# 8. Optional Fields Acceptance
# ===========================================================================


class TestOptionalFields:
    """Vibe rules may include optional metadata fields like importance and examples."""

    def test_importance_field_accepted(self, tmp_path: Path) -> None:
        """Schema validation accepts vibes with importance field."""
        policy = {
            "vibes": {
                "TEST": {
                    "description": "test vibe",
                    "enabled": True,
                    "default_domain": "std",
                    "importance": 0.5,
                }
            }
        }
        f = tmp_path / "p.json"
        f.write_text(json.dumps(policy), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        errors = ld.validate_policy_schema(policy)
        assert errors == []

    def test_examples_field_accepted(self, tmp_path: Path) -> None:
        """Schema validation accepts vibes with examples field."""
        policy = {
            "vibes": {
                "TEST": {
                    "description": "test vibe",
                    "enabled": True,
                    "default_domain": "std",
                    "examples": ["query one", "query two"],
                }
            }
        }
        f = tmp_path / "p.json"
        f.write_text(json.dumps(policy), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        errors = ld.validate_policy_schema(policy)
        assert errors == []

    def test_both_optional_fields_together(self, tmp_path: Path) -> None:
        """Schema validation accepts vibes with both importance and examples."""
        policy = {
            "vibes": {
                "TEST": {
                    "description": "test vibe",
                    "enabled": True,
                    "default_domain": "std",
                    "importance": 0.1,
                    "examples": ["how are things?", "hello"],
                }
            }
        }
        f = tmp_path / "p.json"
        f.write_text(json.dumps(policy), encoding="utf-8")
        ld = TriagePolicyLoader(policy_path=f)
        errors = ld.validate_policy_schema(policy)
        assert errors == []
