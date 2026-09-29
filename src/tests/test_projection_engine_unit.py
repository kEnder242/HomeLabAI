#!/usr/bin/env python3
"""
[FEAT-603 / FEAT-622 / WIS-487] Sprint 94.6 -- Consolidated Projection Engine
Backend Package: unit test suite.

Covers all four modules plus the package export surface:
  1. projection.bones       -- DocumentAST/DocumentNode, extract_bones,
                               reconcile_diff, legacy paper-AST normalization.
  2. projection.lenses      -- POWER_VERBS, WEAK_OPENINGS, craft_lens
                               (incl. the UNSAFE_TO_CRAFT refusal branch),
                               validate_lens_schema, tier partition, budget.
  3. projection.engine      -- ProjectionEngine.project: rule adjudication,
                               flag attachment, candidate diff, drift metrics.
  4. projection.recommender -- TopicAlignmentMatrix, RecommendationRouter
                               (triage, mutation proposals, cover letters).

These are isolated, hermetic unit tests (BKM-024 fast path). No live daemon,
no network, no LLM, no Portfolio_Dev filesystem dependency. Silicon validation
is performed post-dispatch by the orchestrator.
"""

import copy
import json
import os
import pathlib
import sys

import pytest

# Resolve the package regardless of the invoking rootdir.
_HOMELAB_SRC = "/home/jallred/Dev_Lab/HomeLabAI/src"
if _HOMELAB_SRC not in sys.path:
    sys.path.insert(0, _HOMELAB_SRC)

import projection
from projection.bones import (
    BONE_SCHEMA_VERSION,
    DocumentAST,
    DocumentNode,
    extract_bones,
    normalize_ast,
    reconcile_diff,
)
from projection.engine import MAX_BULLETS_PER_BONE, ProjectionEngine
from projection.lenses import (
    DEFAULT_DETECTOR_BUDGET,
    MIN_CONTENT_CHARS,
    POWER_VERBS,
    UNSAFE_TO_CRAFT,
    WEAK_OPENINGS,
    craft_lens,
    persist_lens,
    validate_lens_schema,
)
from projection.recommender import (
    RecommendationRouter,
    TopicAlignmentMatrix,
)

VALID_SOURCE = "Ex-Google Rubric Playbook: reward high-signal proof points."

# BKM-015: these rules are judge territory. No tier_0 rule may carry them.
SEMANTIC_RULE_IDS = frozenset(
    {
        "FIRST_3_WORDS_POWER_VERB",
        "SO_WHAT_METRIC_DRILL",
        "THREE_SENTENCE_SUMMARY_HOOK",
    }
)
LENS_ID = "farah_sharghi_recruiter_v1"

SPEC_EXPORTS = (
    "DocumentNode",
    "DocumentAST",
    "extract_bones",
    "reconcile_diff",
    "craft_lens",
    "validate_lens_schema",
    "POWER_VERBS",
    "WEAK_OPENINGS",
    "ProjectionEngine",
    "TopicAlignmentMatrix",
    "RecommendationRouter",
)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def canonical_ast():
    """A clean canonical AST that violates no structural rule."""
    return {
        "paper_id": "PAPER-CANON",
        "title": "Canonical Paper",
        "sections": [
            {
                "id": "sec_summary",
                "heading": "Professional Summary",
                "paragraphs": ["Architected telemetry for 12k nodes."],
                "citations": ["FEAT-603"],
                "review_flags": [],
            },
            {
                "id": "sec_experience",
                "heading": "Experience",
                "paragraphs": ["Owned a 40 node fleet across 3 sites."],
                "citations": ["BKM-015"],
                "review_flags": [],
            },
        ],
        "metadata": {"revision_id": "v1_baseline"},
    }


@pytest.fixture
def legacy_ast():
    """The real Paper AST v1/v2 shape consumed by lens_service.grade_paper."""
    return {
        "paper_id": "PAPER-RESUME",
        "revision_id": "v1_baseline",
        "title": "Legacy Resume",
        "author": "Jason Allred",
        "contact": {"email": "kEnder242@gmail.com"},
        "style_schema_ref": "data/papers/style_resume_v1.json",
        "sections": [
            {
                "section_id": "sec_title",
                "heading": "Target Title",
                "nodes": [
                    {
                        "node_id": "node_title_01",
                        "type": "title",
                        "text": "Senior Platform Engineer",
                        "citations": ["FEAT-603"],
                        "review_flags": [],
                    }
                ],
            },
            {
                "section_id": "sec_experience",
                "heading": "Experience",
                "roles": [
                    {
                        "role_id": "role_1",
                        "context_line": "Owned 40 node fleet across 3 sites.",
                        "review_flags": [],
                        "bullets": [
                            {
                                "node_id": "b1",
                                "text": "Architected telemetry pipeline for 12k nodes.",
                                "citations": ["BKM-015"],
                            },
                            {
                                "node_id": "b2",
                                "text": "Reduced fleet boot time by 40%.",
                                "citations": [],
                            },
                        ],
                    }
                ],
            },
        ],
    }


@pytest.fixture
def dirty_ast():
    """A document violating several structural rules across three bones.

    Expected tier_0 flags (5 total):
      sec_summary    -> QUANTIFIED_ANCHOR_PRESENT, DNA_CITATION_CONNECTION
      sec_experience -> QUANTIFIED_ANCHOR_PRESENT, DNA_CITATION_CONNECTION
      sec_skills     -> QUANTIFIED_ANCHOR_PRESENT
    """
    return {
        "paper_id": "PAPER-DIRTY",
        "title": "Dirty Paper",
        "sections": [
            {
                "id": "sec_summary",
                "heading": "Summary",
                "paragraphs": ["Delivered platform work without metrics."],
                "citations": [],
            },
            {
                "id": "sec_experience",
                "heading": "Experience",
                "paragraphs": ["Owned infrastructure."],
                "citations": [],
            },
            {
                "id": "sec_skills",
                "heading": "Skills",
                "paragraphs": ["No numbers here."],
                "citations": ["FEAT-1"],
            },
        ],
    }


@pytest.fixture
def compiled_lens():
    """A successfully compiled lens envelope."""
    return craft_lens(LENS_ID, VALID_SOURCE, "Farah Sharghi Recruiter Lens")


def _rebudget(lens, **overrides):
    """Clone a lens envelope with a mutated detector budget."""
    clone = copy.deepcopy(lens)
    clone["rubric"]["detector_budget"].update(overrides)
    return clone


# --------------------------------------------------------------------------
# 0. Package export surface
# --------------------------------------------------------------------------


class TestPackageExports:
    def test_all_spec_symbols_are_exported(self):
        for name in SPEC_EXPORTS:
            assert hasattr(projection, name), f"projection.{name} is not exported"
            assert name in projection.__all__, f"{name} missing from __all__"

    def test_all_symbols_resolve_to_callable_or_type(self):
        for name in SPEC_EXPORTS:
            assert getattr(projection, name) is not None

    def test_version_is_declared(self):
        assert isinstance(projection.__version__, str)
        assert projection.__version__.count(".") >= 1

    def test_star_import_surface_matches_all(self):
        namespace = {}
        exec("from projection import *", namespace)  # noqa: S102
        for name in projection.__all__:
            assert name in namespace

    def test_submodules_are_reachable(self):
        from projection import bones, engine, lenses, recommender

        for module in (bones, engine, lenses, recommender):
            assert module.__name__.startswith("projection.")


# --------------------------------------------------------------------------
# 1. bones.py
# --------------------------------------------------------------------------


class TestDocumentNode:
    def test_defaults_are_isolated_per_instance(self):
        a, b = DocumentNode(id="a", heading="A"), DocumentNode(id="b", heading="B")
        a.paragraphs.append("x")
        assert b.paragraphs == []

    def test_roundtrip_is_faithful(self):
        node = DocumentNode(
            id="sec_x",
            heading="Heading",
            paragraphs=["a", "b"],
            citations=["FEAT-1"],
            review_flags=[{"id": "f1", "status": "OPEN"}],
        )
        assert DocumentNode.from_dict(node.to_dict()) == node

    def test_from_dict_accepts_section_id_alias(self):
        node = DocumentNode.from_dict({"section_id": "sec_legacy", "heading": "H"})
        assert node.id == "sec_legacy"

    def test_review_flags_are_copied_not_aliased(self):
        node = DocumentNode(id="a", heading="A")
        payload = node.to_dict()
        payload["review_flags"].append({"id": "injected"})
        assert node.review_flags == []

    def test_checksum_is_stable_and_content_sensitive(self):
        a = DocumentNode(id="a", heading="H", paragraphs=["Reduced latency 40%"])
        b = DocumentNode(id="a", heading="H", paragraphs=["Reduced latency 40%"])
        c = DocumentNode(id="a", heading="H", paragraphs=["Reduced latency 90%"])
        assert a.checksum() == b.checksum()
        assert a.checksum() != c.checksum()

    def test_checksum_ignores_punctuation_and_case(self):
        a = DocumentNode(id="a", heading="H", paragraphs=["Built 3 Systems, Fast!"])
        b = DocumentNode(id="a", heading="H", paragraphs=["built 3 systems fast"])
        assert a.checksum() == b.checksum()


class TestDocumentAST:
    def test_roundtrip_is_faithful(self, canonical_ast):
        ast = DocumentAST.from_dict(canonical_ast)
        assert DocumentAST.from_dict(ast.to_dict()).to_dict() == ast.to_dict()

    def test_to_dict_is_json_serializable(self, canonical_ast):
        assert json.loads(json.dumps(DocumentAST.from_dict(canonical_ast).to_dict()))

    def test_from_dict_tolerates_sections_as_node_objects(self, canonical_ast):
        ast = DocumentAST.from_dict(canonical_ast)
        payload = ast.to_dict()
        payload["sections"] = [DocumentNode(id="sec_x", heading="X")]
        assert DocumentAST.from_dict(payload).sections[0].id == "sec_x"


class TestNormalizeAST:
    def test_canonical_dict_passes_through(self, canonical_ast):
        ast = normalize_ast(canonical_ast)
        assert [s.id for s in ast.sections] == ["sec_summary", "sec_experience"]
        assert ast.sections[0].paragraphs == ["Architected telemetry for 12k nodes."]

    def test_document_ast_instance_is_returned_unchanged(self, canonical_ast):
        ast = DocumentAST.from_dict(canonical_ast)
        assert normalize_ast(ast) is ast

    def test_legacy_nodes_are_flattened(self, legacy_ast):
        title = normalize_ast(legacy_ast).sections[0]
        assert title.id == "sec_title"
        assert title.paragraphs == ["Senior Platform Engineer"]
        assert title.citations == ["FEAT-603"]

    def test_legacy_roles_and_bullets_are_flattened(self, legacy_ast):
        experience = normalize_ast(legacy_ast).sections[1]
        assert experience.paragraphs == [
            "Owned 40 node fleet across 3 sites.",
            "[b1] Architected telemetry pipeline for 12k nodes.",
            "[b2] Reduced fleet boot time by 40%.",
        ]
        assert experience.citations == ["BKM-015"]

    def test_unknown_top_level_keys_preserved_in_metadata(self, legacy_ast):
        meta = normalize_ast(legacy_ast).metadata
        assert meta["author"] == "Jason Allred"
        assert meta["revision_id"] == "v1_baseline"
        assert meta["style_schema_ref"] == "data/papers/style_resume_v1.json"

    def test_normalization_is_idempotent(self, legacy_ast):
        once = normalize_ast(legacy_ast)
        twice = normalize_ast(once.to_dict())
        assert [s.id for s in once.sections] == [s.id for s in twice.sections]
        assert [s.paragraphs for s in once.sections] == [s.paragraphs for s in twice.sections]

    def test_non_dict_non_ast_is_rejected(self):
        with pytest.raises(TypeError):
            normalize_ast("not a document")

    def test_missing_sections_yields_empty_ast(self):
        assert normalize_ast({"paper_id": "P", "title": "T"}).sections == []


class TestExtractBones:
    def test_bone_shape_and_schema_tag(self, canonical_ast):
        bone = extract_bones(canonical_ast)[0]
        assert bone["schema"] == BONE_SCHEMA_VERSION
        assert bone["bone_id"] == "PAPER-CANON::sec_summary"
        assert bone["position"] == 0
        assert bone["heading"] == "Professional Summary"
        assert bone["citations"] == ["FEAT-603"]
        assert len(bone["anchor_checksum"]) == 16
        assert len(bone["content_checksum"]) == 16

    def test_bones_are_json_serializable(self, legacy_ast):
        assert json.loads(json.dumps(extract_bones(legacy_ast)))

    def test_extraction_is_deterministic(self, legacy_ast):
        assert extract_bones(legacy_ast) == extract_bones(legacy_ast)

    def test_accepts_document_ast_instance(self, canonical_ast):
        assert len(extract_bones(DocumentAST.from_dict(canonical_ast))) == 2

    def test_bone_id_falls_back_to_section_id_without_paper(self):
        bones = extract_bones({"title": "T", "sections": [{"id": "sec_a", "heading": "A"}]})
        assert bones[0]["bone_id"] == "sec_a"

    def test_anchor_checksum_tracks_identity_not_prose(self, canonical_ast):
        revised = copy.deepcopy(canonical_ast)
        revised["sections"][0]["paragraphs"] = ["Totally different prose about 7 nodes."]
        before = extract_bones(canonical_ast)[0]
        after = extract_bones(revised)[0]
        assert before["anchor_checksum"] == after["anchor_checksum"]
        assert before["content_checksum"] != after["content_checksum"]


class TestReconcileDiff:
    def test_identical_revisions_are_reconciled(self, canonical_ast):
        bones = {"bones": extract_bones(canonical_ast)}
        diff = reconcile_diff(bones, bones)
        assert diff["is_reconciled"] is True
        assert diff["drift"] == 0.0
        assert diff["added"] == [] and diff["removed"] == [] and diff["modified"] == []
        assert diff["unchanged_count"] == 2

    def test_added_and_removed_bones_are_reported(self, canonical_ast):
        original = {"bones": extract_bones(canonical_ast)}
        revised_doc = copy.deepcopy(canonical_ast)
        revised_doc["sections"] = revised_doc["sections"][:1]
        diff = reconcile_diff(original, {"bones": extract_bones(revised_doc)})
        assert diff["removed"] == ["PAPER-CANON::sec_experience"]
        assert diff["added"] == []
        assert diff["is_reconciled"] is False
        # One changed identity out of a two-bone union.
        assert diff["drift"] == 0.5

    def test_added_bone_detected(self, canonical_ast):
        revised = copy.deepcopy(canonical_ast)
        revised["sections"].append({"id": "sec_new", "heading": "New", "paragraphs": ["5 items"]})
        diff = reconcile_diff({"bones": extract_bones(canonical_ast)}, {"bones": extract_bones(revised)})
        assert diff["added"] == ["PAPER-CANON::sec_new"]
        assert diff["removed"] == []

    def test_modified_bone_reports_checksum_transition(self, canonical_ast):
        revised = copy.deepcopy(canonical_ast)
        revised["sections"][0]["paragraphs"] = ["Rebuilt the fleet for 900 nodes."]
        diff = reconcile_diff({"bones": extract_bones(canonical_ast)}, {"bones": extract_bones(revised)})
        assert len(diff["modified"]) == 1
        assert diff["modified"][0]["bone_id"] == "PAPER-CANON::sec_summary"
        assert diff["modified"][0]["content_checksum_before"] != diff["modified"][0]["content_checksum_after"]

    def test_flag_deltas_tracked_independently_of_prose(self, canonical_ast):
        original = extract_bones(canonical_ast)
        flagged = copy.deepcopy(original)
        flagged[0]["review_flags"] = [{"id": "PAPER-CANON::sec_summary::X"}]
        diff = reconcile_diff({"bones": original}, {"bones": flagged})
        assert diff["drift"] == 0.0, "prose is unchanged, so structural drift stays zero"
        assert diff["flags_added_total"] == 1
        assert diff["flag_drift"] == 0.5
        assert diff["is_reconciled"] is False
        assert diff["flag_deltas"][0]["flags_added"] == ["PAPER-CANON::sec_summary::X"]

    def test_accepts_bare_bone_lists(self, canonical_ast):
        bones = extract_bones(canonical_ast)
        assert reconcile_diff(bones, bones)["is_reconciled"] is True

    def test_accepts_raw_document_dicts(self, canonical_ast):
        assert reconcile_diff(canonical_ast, canonical_ast)["is_reconciled"] is True

    def test_empty_inputs_do_not_divide_by_zero(self):
        diff = reconcile_diff({"bones": []}, {"bones": []})
        assert diff["drift"] == 0.0 and diff["flag_drift"] == 0.0

    def test_diff_is_json_serializable(self, canonical_ast):
        diff = reconcile_diff({"bones": extract_bones(canonical_ast)}, {"bones": extract_bones(canonical_ast)})
        assert json.loads(json.dumps(diff))


# --------------------------------------------------------------------------
# 2. lenses.py
# --------------------------------------------------------------------------


class TestVocabularies:
    def test_power_verbs_is_a_non_empty_lowercase_string_set(self):
        assert isinstance(POWER_VERBS, set)
        assert len(POWER_VERBS) > 10
        assert all(isinstance(v, str) and v.islower() for v in POWER_VERBS)

    def test_power_verbs_cover_the_incumbent_vocabulary(self):
        for verb in ("architected", "engineered", "spearheaded", "standardized", "drove"):
            assert verb in POWER_VERBS

    def test_weak_openings_are_phrase_replacement_tuples(self):
        assert isinstance(WEAK_OPENINGS, list)
        assert len(WEAK_OPENINGS) >= 6
        for entry in WEAK_OPENINGS:
            assert isinstance(entry, tuple) and len(entry) == 2
            weak_phrase, replacement = entry
            assert isinstance(weak_phrase, str) and weak_phrase
            assert isinstance(replacement, str) and replacement

    def test_weak_openings_cover_passive_constructions(self):
        phrases = [p for p, _ in WEAK_OPENINGS]
        assert "responsible for" in phrases and "worked on" in phrases


class TestCraftLensSuccess:
    def test_success_envelope_shape(self, compiled_lens):
        assert compiled_lens["status"] == "success"
        assert compiled_lens["lens_id"] == LENS_ID
        assert isinstance(compiled_lens["rubric"], dict)

    def test_compiled_lens_validates(self, compiled_lens):
        assert validate_lens_schema(compiled_lens) is True

    def test_title_defaults_from_lens_id(self):
        assert craft_lens("my_lens_id", VALID_SOURCE)["rubric"]["title"] == "My Lens Id"

    def test_explicit_title_wins(self, compiled_lens):
        assert compiled_lens["rubric"]["title"] == "Farah Sharghi Recruiter Lens"

    def test_persona_is_merged_over_defaults(self):
        lens = craft_lens(LENS_ID, VALID_SOURCE, persona={"name": "Custom Reviewer"})
        assert lens["rubric"]["persona"]["name"] == "Custom Reviewer"
        assert lens["rubric"]["persona"]["role"]  # default preserved

    def test_source_snippet_is_bounded(self):
        lens = craft_lens(LENS_ID, "word " * 500)
        assert len(lens["rubric"]["source_snippet"]) <= 300
        assert lens["rubric"]["source_chars"] > 300

    def test_rules_are_mirrored_on_both_keys(self, compiled_lens):
        rubric = compiled_lens["rubric"]
        assert rubric["rules"] == rubric["rubric_rules"]

    def test_criteria_extend_the_rule_set(self):
        criteria = [{
            "rule_id": "CUSTOM_RULE",
            "category": "PROSE",
            "target": "bone_paragraphs",
            "severity": "HIGH",
            "tier": "tier_0_structural",
            "description": "Custom deterministic check.",
        }]
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria=criteria)
        assert "CUSTOM_RULE" in [r["rule_id"] for r in lens["rubric"]["rules"]]

    def test_duplicate_criteria_are_deduplicated(self):
        criteria = [{"rule_id": "SO_WHAT_METRIC_DRILL", "severity": "LOW", "tier": "tier_1_semantic"}]
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria=criteria)
        ids = [r["rule_id"] for r in lens["rubric"]["rules"]]
        assert ids.count("SO_WHAT_METRIC_DRILL") == 1

    def test_lens_id_is_whitespace_trimmed(self):
        assert craft_lens("  spaced_lens  ", VALID_SOURCE)["lens_id"] == "spaced_lens"

    def test_compilation_is_deterministic(self):
        assert craft_lens(LENS_ID, VALID_SOURCE) == craft_lens(LENS_ID, VALID_SOURCE)


class TestCraftLensRefusals:
    """WIS-487: total function compilation. No silent default fallback."""

    @pytest.mark.parametrize(
        "content",
        ["", "   ", "\n\t  ", None, 123, [], {}, b"bytes"],
    )
    def test_invalid_content_is_refused(self, content):
        lens = craft_lens(LENS_ID, content)
        assert lens["status"] == UNSAFE_TO_CRAFT
        assert lens["lens_id"] == LENS_ID
        assert lens["reason"]
        assert "rubric" not in lens

    def test_short_content_is_refused_with_length_reason(self):
        lens = craft_lens(LENS_ID, "hi")
        assert lens["status"] == UNSAFE_TO_CRAFT
        assert str(MIN_CONTENT_CHARS) in lens["reason"]

    def test_content_just_over_minimum_compiles(self):
        assert craft_lens(LENS_ID, "x" * (MIN_CONTENT_CHARS + 1))["status"] == "success"

    @pytest.mark.parametrize("lens_id", ["", "   ", None, 42])
    def test_invalid_lens_id_is_refused(self, lens_id):
        assert craft_lens(lens_id, VALID_SOURCE)["status"] == UNSAFE_TO_CRAFT

    def test_non_list_criteria_refused(self):
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria="nope")
        assert lens["status"] == UNSAFE_TO_CRAFT and "criteria must be a list" in lens["reason"]

    def test_criteria_without_rule_id_refused(self):
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria=[{"severity": "HIGH"}])
        assert lens["status"] == UNSAFE_TO_CRAFT and "rule_id" in lens["reason"]

    def test_criteria_with_unknown_severity_refused(self):
        criteria = [{"rule_id": "R", "severity": "APOCALYPTIC"}]
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria=criteria)
        assert lens["status"] == UNSAFE_TO_CRAFT and "severity" in lens["reason"]

    def test_criteria_with_unknown_tier_refused(self):
        criteria = [{"rule_id": "R", "tier": "tier_9_bogus"}]
        assert craft_lens(LENS_ID, VALID_SOURCE, criteria=criteria)["status"] == UNSAFE_TO_CRAFT

    def test_non_dict_criteria_refused(self):
        assert craft_lens(LENS_ID, VALID_SOURCE, criteria=["a"])["status"] == UNSAFE_TO_CRAFT

    def test_non_dict_persona_refused(self):
        lens = craft_lens(LENS_ID, VALID_SOURCE, persona=["a"])
        assert lens["status"] == UNSAFE_TO_CRAFT and "persona must be a dict" in lens["reason"]

    def test_non_string_title_refused(self):
        assert craft_lens(LENS_ID, VALID_SOURCE, title=7)["status"] == UNSAFE_TO_CRAFT

    def test_refusal_never_raises(self):
        for bad in (None, object(), 3.5):
            assert craft_lens(LENS_ID, bad)["status"] == UNSAFE_TO_CRAFT

    def test_refusal_is_json_serializable(self):
        assert json.loads(json.dumps(craft_lens(LENS_ID, "")))


class TestTierPartition:
    """BKM-015: no semantic grading may sit in the structural tier."""


    def test_manifest_covers_every_rule_exactly_once(self, compiled_lens):
        rubric = compiled_lens["rubric"]
        tier_0 = rubric["tier_manifest"]["tier_0_structural"]
        tier_1 = rubric["tier_manifest"]["tier_1_semantic"]
        assert sorted(tier_0 + tier_1) == sorted(r["rule_id"] for r in rubric["rules"])
        assert not set(tier_0) & set(tier_1)

    def test_semantic_rules_are_declared_in_tier_1(self, compiled_lens):
        tier_1 = compiled_lens["rubric"]["tier_manifest"]["tier_1_semantic"]
        assert SEMANTIC_RULE_IDS <= set(tier_1)

    def test_no_semantic_rule_sits_in_tier_0(self, compiled_lens):
        tier_0 = compiled_lens["rubric"]["tier_manifest"]["tier_0_structural"]
        assert not SEMANTIC_RULE_IDS & set(tier_0)

    def test_judge_contract_pins_temperature_and_output(self, compiled_lens):
        contract = compiled_lens["rubric"]["judge_contract"]
        assert contract["temperature"] == 0
        assert contract["output"] == "structured_json"
        assert contract["resolves"] == "tier_1_semantic"

    def test_default_budget_is_exposed_and_positive(self, compiled_lens):
        budget = compiled_lens["rubric"]["detector_budget"]
        assert budget == DEFAULT_DETECTOR_BUDGET
        assert all(isinstance(v, int) and v > 0 for v in budget.values())

    def test_base_rule_set_fits_the_default_budget(self, compiled_lens):
        rubric = compiled_lens["rubric"]
        budget = rubric["detector_budget"]
        assert len(rubric["tier_manifest"]["tier_0_structural"]) <= budget["tier_0"]
        assert len(rubric["tier_manifest"]["tier_1_semantic"]) <= budget["tier_1"]

    def test_budget_overflow_is_reported_not_silently_dropped(self):
        criteria = [
            {"rule_id": f"OVERFLOW_{i:02d}", "tier": "tier_1_semantic", "severity": "LOW"}
            for i in range(12)
        ]
        lens = craft_lens(LENS_ID, VALID_SOURCE, criteria=criteria)
        rubric = lens["rubric"]
        assert rubric["budget_exceeded"], "overflow must be reported explicitly"
        assert len(rubric["tier_manifest"]["tier_1_semantic"]) <= rubric["detector_budget"]["tier_1"]
        assert validate_lens_schema(lens) is True


class TestValidateLensSchema:
    def test_accepts_envelope(self, compiled_lens):
        assert validate_lens_schema(compiled_lens) is True

    def test_accepts_bare_rubric(self, compiled_lens):
        assert validate_lens_schema(compiled_lens["rubric"]) is True

    @pytest.mark.parametrize("payload", [None, "lens", 42, [], True])
    def test_rejects_non_dict(self, payload):
        assert validate_lens_schema(payload) is False

    def test_rejects_empty_dict(self):
        assert validate_lens_schema({}) is False

    def test_rejects_refusal_envelope(self):
        assert validate_lens_schema(craft_lens(LENS_ID, "")) is False

    @pytest.mark.parametrize("missing", ["schema", "lens_id", "title", "persona", "rules", "detector_budget"])
    def test_rejects_missing_required_key(self, compiled_lens, missing):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        del rubric[missing]
        assert validate_lens_schema({"rubric": rubric}) is False

    def test_rejects_blank_lens_id(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["lens_id"] = "   "
        assert validate_lens_schema(rubric) is False

    def test_rejects_non_dict_persona(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["persona"] = "nope"
        assert validate_lens_schema(rubric) is False

    def test_rejects_empty_rule_list(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["rules"] = []
        assert validate_lens_schema(rubric) is False

    def test_rejects_duplicate_rule_ids(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["rules"] = rubric["rules"] + [copy.deepcopy(rubric["rules"][0])]
        assert validate_lens_schema(rubric) is False

    @pytest.mark.parametrize("field", ["rule_id", "category", "target", "severity", "tier", "description"])
    def test_rejects_rule_missing_field(self, compiled_lens, field):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        del rubric["rules"][0][field]
        assert validate_lens_schema(rubric) is False

    def test_rejects_unknown_severity_enum(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["rules"][0]["severity"] = "NUCLEAR"
        assert validate_lens_schema(rubric) is False

    def test_rejects_unknown_tier_enum(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["rules"][0]["tier"] = "tier_2_bogus"
        assert validate_lens_schema(rubric) is False

    def test_rejects_semantic_rule_smuggled_into_tier_0(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        for rule in rubric["rules"]:
            if rule["rule_id"] == "FIRST_3_WORDS_POWER_VERB":
                rule["tier"] = "tier_0_structural"
        assert validate_lens_schema(rubric) is False

    @pytest.mark.parametrize("value", [0, -1, "8", None])
    def test_rejects_non_positive_budget(self, compiled_lens, value):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["detector_budget"]["tier_0"] = value
        assert validate_lens_schema(rubric) is False

    def test_rejects_rules_exceeding_budget(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["detector_budget"]["tier_0"] = 1
        assert validate_lens_schema(rubric) is False

    def test_rejects_partial_tier_manifest(self, compiled_lens):
        rubric = copy.deepcopy(compiled_lens["rubric"])
        rubric["tier_manifest"] = {"tier_0_structural": []}
        assert validate_lens_schema(rubric) is False

    def test_never_raises_on_hostile_payload(self):
        hostile = {"rubric": {"rules": [{"rule_id": {"nested": 1}}], "detector_budget": []}}
        assert validate_lens_schema(hostile) is False


class TestHermeticity:
    def test_craft_lens_writes_no_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        before = set(os.listdir(tmp_path))
        craft_lens(LENS_ID, VALID_SOURCE)
        craft_lens("refused_lens", "")
        assert set(os.listdir(tmp_path)) == before

    def test_persist_lens_writes_atomically(self, tmp_path, compiled_lens):
        path = persist_lens(compiled_lens, tmp_path / "lenses")
        assert os.path.exists(path)
        assert not list((tmp_path / "lenses").glob("*.tmp"))
        assert json.loads(pathlib.Path(path).read_text())["lens_id"] == LENS_ID

    def test_persist_lens_rejects_uncompiled_input(self, tmp_path):
        with pytest.raises(ValueError):
            persist_lens(craft_lens(LENS_ID, ""), tmp_path)


# --------------------------------------------------------------------------
# 3. engine.py
# --------------------------------------------------------------------------


class TestProjectionEngine:
    def test_success_envelope_keys(self, canonical_ast, compiled_lens):
        result = ProjectionEngine().project(canonical_ast, compiled_lens)
        for key in (
            "status", "paper_id", "lens_id", "revision_id", "bones", "candidate_bones",
            "candidate_ast", "review_flags", "total_review_flags", "advisories",
            "advisory_count", "candidate_diff", "drift", "detector_budget", "budget_truncated",
        ):
            assert key in result, f"missing envelope key: {key}"
        assert result["status"] == "success"
        assert result["paper_id"] == "PAPER-CANON"
        assert result["lens_id"] == LENS_ID

    def test_clean_document_raises_no_structural_flags(self, canonical_ast, compiled_lens):
        result = ProjectionEngine().project(canonical_ast, compiled_lens)
        assert result["total_review_flags"] == 0
        assert result["review_flags"] == []

    def test_canonical_document_still_emits_tier_1_evidence(self, canonical_ast, compiled_lens):
        result = ProjectionEngine().project(canonical_ast, compiled_lens)
        assert result["advisory_count"] > 0

    def test_only_tier_0_rules_produce_review_flags(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        assert result["review_flags"]
        assert {f["tier"] for f in result["review_flags"]} == {"tier_0_structural"}

    def test_tier_1_rules_are_never_auto_resolved(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        flagged = {f["rule_id"] for f in result["review_flags"]}
        advisory_rules = {a["rule_id"] for a in result["advisories"]}
        assert "FIRST_3_WORDS_POWER_VERB" not in flagged
        assert "FIRST_3_WORDS_POWER_VERB" in advisory_rules
        assert {a["status"] for a in result["advisories"]} == {"PENDING_JUDGE"}
        assert all(a["advisory"] is True for a in result["advisories"])

    def test_advisories_carry_judge_evidence(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        power = next(a for a in result["advisories"] if a["rule_id"] == "FIRST_3_WORDS_POWER_VERB")
        assert power["evidence"]["kind"] == "opening_token_sample"
        assert power["evidence"]["tokens"] == ["Senior", "Platform", "Engineer"]
        assert power["evidence"]["in_power_verb_vocabulary"] is False
        assert power["adjudicator"] == "tier_1_semantic"

    def test_passive_opening_is_evidence_not_a_flag(self):
        doc = {
            "paper_id": "P",
            "title": "T",
            "sections": [{
                "id": "sec_experience", "heading": "Experience",
                "paragraphs": ["Worked on 12k node fleet for 3 years."],
                "citations": ["FEAT-1"],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        assert result["total_review_flags"] == 0
        advisory = next(a for a in result["advisories"] if a["rule_id"] == "FIRST_3_WORDS_POWER_VERB")
        assert advisory["evidence"]["kind"] == "passive_opening_match"
        assert advisory["evidence"]["suggested_replacement"]

    def test_missing_citation_is_flagged(self):
        doc = {
            "paper_id": "P", "title": "T",
            "sections": [{
                "id": "sec_summary", "heading": "Summary",
                "paragraphs": ["Shipped 4 datacenters."], "citations": [],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        assert [f["rule_id"] for f in result["review_flags"]] == ["DNA_CITATION_CONNECTION"]

    def test_missing_quantified_anchor_is_flagged(self):
        doc = {
            "paper_id": "P", "title": "T",
            "sections": [{
                "id": "sec_summary", "heading": "Summary",
                "paragraphs": ["Delivered platform reliability work."], "citations": ["FEAT-1"],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        assert [f["rule_id"] for f in result["review_flags"]] == ["QUANTIFIED_ANCHOR_PRESENT"]

    def test_bullet_density_cap_flagged_above_threshold(self):
        doc = {
            "paper_id": "P", "title": "T",
            "sections": [{
                "id": "sec_summary", "heading": "Summary",
                "paragraphs": [f"Achievement {i} for 3 teams." for i in range(MAX_BULLETS_PER_BONE + 1)],
                "citations": ["FEAT-1"],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        assert "BULLET_DENSITY_CAP" in {f["rule_id"] for f in result["review_flags"]}

    def test_role_bone_without_purview_is_flagged(self):
        doc = {
            "paper_id": "P", "title": "T",
            "sections": [{
                "id": "sec_experience", "heading": "Experience",
                "paragraphs": [], "citations": ["FEAT-1"],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        assert "CONTEXT_LINE_PURVIEW" in {f["rule_id"] for f in result["review_flags"]}

    def test_flag_ids_are_bone_namespaced(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        for flag in result["review_flags"]:
            assert flag["id"].startswith("PAPER-RESUME::sec_")
            assert flag["bone_id"].startswith("PAPER-RESUME::")
            assert flag["status"] == "OPEN"
            assert flag["suggestion"]

    def test_flags_sorted_by_severity(self):
        doc = {
            "paper_id": "P", "title": "T",
            "sections": [{
                "id": "sec_summary", "heading": "S",
                "paragraphs": ["No numbers here at all."], "citations": [],
            }],
        }
        result = ProjectionEngine().project(doc, craft_lens(LENS_ID, VALID_SOURCE))
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        ranks = [order[f["severity"]] for f in result["review_flags"]]
        assert ranks == sorted(ranks)

    def test_max_flags_per_node_budget_is_enforced(self, dirty_ast, compiled_lens):
        lens = _rebudget(compiled_lens, max_flags_per_node=1)
        result = ProjectionEngine().project(dirty_ast, lens)
        per_bone = {}
        for flag in result["review_flags"]:
            per_bone[flag["bone_id"]] = per_bone.get(flag["bone_id"], 0) + 1
        assert all(count <= 1 for count in per_bone.values())
        assert result["budget_truncated"]

    def test_max_total_flags_budget_is_enforced(self, dirty_ast, compiled_lens):
        lens = _rebudget(compiled_lens, max_total_flags=1)
        result = ProjectionEngine().project(dirty_ast, lens)
        assert result["total_review_flags"] == 1
        assert result["budget_truncated"]

    def test_drift_metrics_shape(self, legacy_ast, compiled_lens):
        drift = ProjectionEngine().project(legacy_ast, compiled_lens)["drift"]
        for key in (
            "structural_drift", "bones_total", "bones_flagged", "flagged_ratio",
            "total_review_flags", "flags_by_severity", "flags_by_category",
            "critical_count", "tier_1_pending", "is_reconciled",
        ):
            assert key in drift, f"missing drift key: {key}"
        assert drift["bones_total"] == 2
        assert 0.0 <= drift["flagged_ratio"] <= 1.0
        assert 0.0 <= drift["structural_drift"] <= 1.0

    def test_candidate_diff_tracks_attached_flags(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        diff = result["candidate_diff"]
        assert diff["flags_added_total"] == result["total_review_flags"]
        assert diff["is_reconciled"] is False

    def test_candidate_ast_carries_flags_onto_sections(self, legacy_ast, compiled_lens):
        candidate = ProjectionEngine().project(legacy_ast, compiled_lens)["candidate_ast"]
        assert candidate["paper_id"] == "PAPER-RESUME"
        flagged = [s for s in candidate["sections"] if s["review_flags"]]
        assert flagged, "candidate AST must expose the attached flags"

    def test_projection_is_idempotent(self, legacy_ast, compiled_lens):
        engine = ProjectionEngine()
        first = engine.project(legacy_ast, compiled_lens)
        second = engine.project(legacy_ast, compiled_lens)
        assert first["review_flags"] == second["review_flags"]
        assert first["drift"] == second["drift"]

    def test_input_document_is_not_mutated(self, canonical_ast, compiled_lens):
        snapshot = copy.deepcopy(canonical_ast)
        ProjectionEngine().project(canonical_ast, compiled_lens)
        assert canonical_ast == snapshot

    def test_works_on_document_ast_instance(self, canonical_ast, compiled_lens):
        result = ProjectionEngine().project(DocumentAST.from_dict(canonical_ast), compiled_lens)
        assert result["status"] == "success"

    def test_lens_can_be_bound_at_construction(self, canonical_ast, compiled_lens):
        result = ProjectionEngine(lens=compiled_lens).project(canonical_ast)
        assert result["status"] == "success" and result["lens_id"] == LENS_ID

    def test_explicit_lens_overrides_bound_lens(self, canonical_ast, compiled_lens):
        other = craft_lens("other_lens", VALID_SOURCE)
        result = ProjectionEngine(lens=compiled_lens).project(canonical_ast, other)
        assert result["lens_id"] == "other_lens"

    def test_bare_rubric_lens_is_accepted(self, canonical_ast, compiled_lens):
        result = ProjectionEngine().project(canonical_ast, compiled_lens["rubric"])
        assert result["status"] == "success"

    def test_result_is_json_serializable(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        assert json.loads(json.dumps(result))

    def test_rejects_missing_lens(self, canonical_ast):
        result = ProjectionEngine().project(canonical_ast)
        assert result["status"] == "LENS_REJECTED"
        assert result["reason"]

    def test_rejects_refused_lens(self, canonical_ast):
        result = ProjectionEngine().project(canonical_ast, craft_lens(LENS_ID, ""))
        assert result["status"] == "LENS_REJECTED"
        assert "empty" in result["reason"]

    def test_rejects_schema_invalid_lens(self, canonical_ast, compiled_lens):
        broken = copy.deepcopy(compiled_lens)
        del broken["rubric"]["detector_budget"]
        result = ProjectionEngine().project(canonical_ast, broken)
        assert result["status"] == "LENS_REJECTED"
        assert "validate_lens_schema" in result["reason"]

    def test_engine_construction_tolerates_no_lens(self):
        assert ProjectionEngine().lens is None


# --------------------------------------------------------------------------
# 4. recommender.py
# --------------------------------------------------------------------------


class TestTopicAlignmentMatrix:
    JD = (
        "Senior datacenter platform engineer with firmware integration, telemetry "
        "analysis and Python automation for automated validation."
    )

    def test_strong_overlap_scores_above_weak(self):
        matrix = TopicAlignmentMatrix()
        strong = matrix.calculate_score(
            "datacenter platform engineer firmware telemetry python automation", self.JD
        )
        weak = matrix.calculate_score("datacenter", self.JD)
        assert 0.0 < weak < strong <= 1.0

    def test_disjoint_topics_score_zero(self):
        assert TopicAlignmentMatrix().calculate_score("pastry baking", self.JD) == 0.0

    def test_perfect_topic_coverage_is_high(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.calculate_score(self.JD, self.JD) > 0.9

    def test_no_overlap_scores_zero(self):
        assert TopicAlignmentMatrix().calculate_score("culinary pastry", self.JD) == 0.0

    @pytest.mark.parametrize("topics,requirements", [("", "x"), ("x", ""), (None, "x"), ("x", None), ([], {})])
    def test_empty_inputs_score_zero(self, topics, requirements):
        assert TopicAlignmentMatrix().calculate_score(topics, requirements) == 0.0

    def test_score_is_bounded(self):
        matrix = TopicAlignmentMatrix()
        for topics in ("a b c d", self.JD, "datacenter"):
            assert 0.0 <= matrix.calculate_score(topics, self.JD) <= 1.0

    def test_nested_containers_are_flattened(self):
        matrix = TopicAlignmentMatrix()
        nested = {"a": ["datacenter", {"b": ["firmware", "telemetry"]}]}
        assert matrix.calculate_score(nested, self.JD) > 0.0

    def test_equivalent_flattening_is_scored_identically(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.calculate_score(
            {"a": ["datacenter", "telemetry"]}, self.JD
        ) == matrix.calculate_score(["datacenter", "telemetry"], self.JD)

    def test_score_is_deterministic(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.calculate_score("datacenter telemetry", self.JD) == matrix.calculate_score(
            "datacenter telemetry", self.JD
        )

    def test_detail_exposes_components(self):
        detail = TopicAlignmentMatrix().score_detail("datacenter telemetry", self.JD)
        assert detail["score"] > 0
        for key in ("coverage", "precision", "jaccard", "matched", "unmatched_requirements"):
            assert key in detail
        assert "datacenter" in detail["matched"]
        assert detail["topic_token_count"] > 0 and detail["requirement_token_count"] > 0

    def test_detail_score_matches_calculate_score(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.score_detail("datacenter", self.JD)["score"] == matrix.calculate_score(
            "datacenter", self.JD
        )

    def test_empty_detail_is_zeroed(self):
        assert TopicAlignmentMatrix().score_detail("", self.JD)["score"] == 0.0

    def test_stopwords_do_not_inflate_score(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.calculate_score("the and of to a", self.JD) == 0.0

    def test_plural_normalization_matches_singular(self):
        matrix = TopicAlignmentMatrix()
        assert matrix.calculate_score("telemetry node", self.JD) == matrix.calculate_score(
            "telemetry nodes", self.JD
        )

    def test_weights_are_normalized(self):
        assert TopicAlignmentMatrix(3, 1).coverage_weight == 0.75
        assert TopicAlignmentMatrix(1, 1).precision_weight == 0.5

    def test_pure_coverage_weight_ranks_broader_topics_higher(self):
        matrix = TopicAlignmentMatrix(coverage_weight=1.0, precision_weight=0.0)
        assert matrix.calculate_score("datacenter telemetry python", self.JD) > matrix.calculate_score(
            "datacenter", self.JD
        )

    def test_zero_weights_rejected(self):
        with pytest.raises(ValueError):
            TopicAlignmentMatrix(0, 0)

    def test_negative_weights_rejected(self):
        with pytest.raises(ValueError):
            TopicAlignmentMatrix(-1, 1)


class TestRouteTriage:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("write me a cover letter for this role", "cover_letter_synthesis"),
            ("expand citations using arxiv papers", "citation_expansion"),
            ("craft a lens rubric for this persona", "lens_crafting"),
            ("what is the drift between these bones", "bone_reconciliation"),
            ("please grade and revise this section", "projection_request"),
            ("how well does this jd match the requirements", "topic_alignment"),
            ("find a new job opening to apply for", "job_search"),
        ],
    )
    def test_intent_families_route_correctly(self, query, expected):
        decision = RecommendationRouter().route_triage(query)
        assert decision["intent"] == expected
        assert decision["handler"]
        assert decision["matched_terms"]
        assert 0.0 < decision["confidence"] <= 1.0

    def test_specificity_beats_generic_job_search(self):
        decision = RecommendationRouter().route_triage("generate a cover letter")
        assert decision["intent"] == "cover_letter_synthesis"

    def test_unmatched_query_falls_back_without_raising(self):
        decision = RecommendationRouter().route_triage("qwertyuiop asdfghjkl")
        assert decision["intent"] == "general_triage"
        assert decision["handler"] is None
        assert decision["confidence"] == 0.0

    @pytest.mark.parametrize("query", ["", "   ", None, 42, [], {}])
    def test_malformed_queries_degrade_gracefully(self, query):
        decision = RecommendationRouter().route_triage(query)
        assert decision["intent"] == "general_triage"
        assert decision["status"] == "success"

    def test_routing_is_case_insensitive(self):
        router = RecommendationRouter()
        assert router.route_triage("COVER LETTER")["intent"] == router.route_triage(
            "cover letter"
        )["intent"]

    def test_routing_is_deterministic(self):
        router = RecommendationRouter()
        assert router.route_triage("craft a lens") == router.route_triage("craft a lens")

    def test_every_routed_intent_declares_a_handler(self):
        router = RecommendationRouter()
        for query in ("cover letter", "citations", "lens", "drift", "project", "jd match", "job"):
            assert router.route_triage(query)["handler"]


class TestProposeMutations:
    def test_mutations_are_ordered_by_severity(self):
        router = RecommendationRouter()
        flags = [
            {"id": "a", "bone_id": "b", "rule_id": "r", "severity": "LOW", "category": "PROSE", "suggestion": "s", "status": "OPEN"},
            {"id": "b", "bone_id": "b", "rule_id": "r", "severity": "CRITICAL", "category": "PROSE", "suggestion": "s", "status": "OPEN"},
            {"id": "c", "bone_id": "b", "rule_id": "r", "severity": "MEDIUM", "category": "PROSE", "suggestion": "s", "status": "OPEN"},
        ]
        mutations = router.propose_mutations(flags)
        assert [m["severity"] for m in mutations] == ["CRITICAL", "MEDIUM", "LOW"]
        assert [m["mutation_id"] for m in mutations] == ["MUT-001", "MUT-002", "MUT-003"]

    def test_resolved_flags_are_excluded(self):
        router = RecommendationRouter()
        flags = [
            {"id": "a", "severity": "CRITICAL", "status": "RESOLVED"},
            {"id": "b", "severity": "LOW", "status": "OPEN"},
        ]
        assert len(router.propose_mutations(flags)) == 1

    def test_malformed_flags_are_skipped(self):
        assert RecommendationRouter().propose_mutations(["nope", None, 3, {}]) == []

    def test_empty_input_yields_no_mutations(self):
        assert RecommendationRouter().propose_mutations([]) == []
        assert RecommendationRouter().propose_mutations(None) == []

    def test_mutation_carries_action_and_status(self):
        mutation = RecommendationRouter().propose_mutations(
            [{"id": "a", "bone_id": "B::s", "rule_id": "R", "severity": "HIGH", "action": None, "suggestion": "fix it", "status": "OPEN"}]
        )[0]
        assert mutation["action"] == "fix it"
        assert mutation["bone_id"] == "B::s"
        assert mutation["status"] == "PROPOSED"

    def test_accepts_projection_output(self, legacy_ast, compiled_lens):
        result = ProjectionEngine().project(legacy_ast, compiled_lens)
        mutations = RecommendationRouter().propose_mutations(result["review_flags"])
        assert len(mutations) == result["total_review_flags"]


class TestSynthesizeCoverLetter:
    JD = "We need a datacenter platform engineer who can own telemetry and firmware validation."

    def test_letter_is_grounded_in_bone_prose(self, legacy_ast):
        bones = extract_bones(legacy_ast)
        letter = RecommendationRouter().synthesize_cover_letter(bones, self.JD)
        assert "Architected telemetry pipeline for 12k nodes." in letter
        assert "EVIDENCE BASE" in letter
        assert "ALIGNMENT" in letter

    def test_letter_cites_bone_ids(self, legacy_ast):
        letter = RecommendationRouter().synthesize_cover_letter(extract_bones(legacy_ast), self.JD)
        assert "PAPER-RESUME::sec_experience" in letter

    def test_letter_reports_alignment_metrics(self, legacy_ast):
        letter = RecommendationRouter().synthesize_cover_letter(extract_bones(legacy_ast), self.JD)
        assert "Target requirements addressed" in letter
        assert "mean bone alignment" in letter

    def test_refuses_without_grounding(self):
        letter = RecommendationRouter().synthesize_cover_letter(
            [{"bone_id": "X::y", "paragraphs": ["Culinary pastry baking techniques."]}], self.JD
        )
        assert letter.startswith("INSUFFICIENT GROUNDING")
        assert "Refusing to fabricate" in letter

    @pytest.mark.parametrize("job_desc", ["", "   ", None, 42])
    def test_refuses_without_job_description(self, legacy_ast, job_desc):
        letter = RecommendationRouter().synthesize_cover_letter(
            extract_bones(legacy_ast), job_desc
        )
        assert letter.startswith("INSUFFICIENT GROUNDING")
        assert "no job description" in letter

    def test_refuses_on_empty_bones(self):
        assert RecommendationRouter().synthesize_cover_letter([], self.JD).startswith(
            "INSUFFICIENT GROUNDING"
        )

    def test_accepts_a_bone_envelope(self, legacy_ast):
        envelope = {"bones": extract_bones(legacy_ast)}
        assert "Architected telemetry" in RecommendationRouter().synthesize_cover_letter(
            envelope, self.JD
        )

    def test_accepts_raw_document_sections(self, legacy_ast):
        assert "Architected telemetry" in RecommendationRouter().synthesize_cover_letter(
            legacy_ast, self.JD
        )

    def test_synthesis_is_deterministic(self, legacy_ast):
        router = RecommendationRouter()
        bones = extract_bones(legacy_ast)
        assert router.synthesize_cover_letter(bones, self.JD) == router.synthesize_cover_letter(
            bones, self.JD
        )

    def test_evidence_is_capped_at_three(self):
        bones = [
            {
                "bone_id": f"P::s{i}",
                "paragraphs": [f"Delivered datacenter telemetry improvement {i * 10} percent."],
            }
            for i in range(6)
        ]
        letter = RecommendationRouter().synthesize_cover_letter(bones, self.JD)
        assert letter.count("[bone: P::") == 3

    def test_no_evidence_is_invented(self, legacy_ast):
        letter = RecommendationRouter().synthesize_cover_letter(
            extract_bones(legacy_ast), "Pastry chef for a bakery in Paris."
        )
        assert "Architected" not in letter


# --------------------------------------------------------------------------
# 5. End-to-end integration
# --------------------------------------------------------------------------


class TestEndToEnd:
    def test_full_pipeline(self, legacy_ast):
        lens = craft_lens(LENS_ID, VALID_SOURCE, "Farah Sharghi Recruiter Lens")
        assert lens["status"] == "success"

        result = ProjectionEngine().project(legacy_ast, lens)
        assert result["status"] == "success"
        assert result["total_review_flags"] >= 1

        mutations = RecommendationRouter().propose_mutations(result["review_flags"])
        assert mutations

        router = RecommendationRouter()
        decision = router.route_triage("draft a cover letter from these bones")
        assert decision["intent"] == "cover_letter_synthesis"

        letter = router.synthesize_cover_letter(
            result["candidate_bones"],
            "Datacenter platform engineer owning telemetry and firmware validation.",
        )
        assert "Architected telemetry pipeline" in letter

    def test_pipeline_stays_inside_the_detector_budget(self, legacy_ast):
        result = ProjectionEngine().project(legacy_ast, craft_lens(LENS_ID, VALID_SOURCE))
        budget = result["detector_budget"]
        assert result["total_review_flags"] <= budget["max_total_flags"]
        assert result["advisory_count"] >= 0

    def test_reconciliation_closes_the_loop(self, legacy_ast):
        result = ProjectionEngine().project(legacy_ast, craft_lens(LENS_ID, VALID_SOURCE))
        closing = reconcile_diff({"bones": result["bones"]}, {"bones": result["candidate_bones"]})
        assert closing["is_reconciled"] is False
        assert closing["flags_added_total"] == result["total_review_flags"]
