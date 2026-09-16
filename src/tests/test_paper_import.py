"""
[SPR-82.1] Generic Document Ingestion & Two-Tier AST Schema — comprehensive unit suite.
========================================================================================
Verifies:
  • Markdown, plain text, and JSON document import into the canonical two-tier AST
    (bone_collection[] / _candidate_pool[] at Root, Section, and Paragraph levels);
  • hierarchical section parsing with heading-level metadata;
  • bone collection / candidate pool initialization (DISCOVER phase semantics);
  • strict schema validation error handling for invalid documents;
  • POST /paper/import handler behavior (offline — no live daemon required).

Hermetic: parser + validator are exercised directly; the handler is invoked with a
mocked aiohttp request and a patched atomic_write_json so no files are written.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HOME_LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ~/Dev_Lab/HomeLabAI
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(HOME_LAB)), "Portfolio_Dev", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from parse_document_to_ast import (  # noqa: E402  (scripts dir added above)
    DEFAULT_TITLE,
    detect_citations,
    parse_document,
    parse_json_document,
    parse_markdown,
    parse_plain_text,
)
from v5.foyer.validate_paper_schema import validate_paper_dict  # noqa: E402
from src.v5.foyer.router import FoyerRouter  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------
def _valid_ast():
    """A canonical two-tier AST that must pass strict validation."""
    return {
        "id": "PAPER-001",
        "title": "Staff Infrastructure & AI Platforms Resume",
        "bone_collection": ["FEAT-181"],
        "_candidate_pool": ["BKM-010"],
        "sections": [
            {
                "id": "sec-01",
                "heading": "Distributed AI Infrastructure",
                "bone_collection": ["WIS-108"],
                "_candidate_pool": [],
                "paragraphs": [
                    {
                        "id": "p-01",
                        "bullet_type": "paragraph",
                        "text": "Architected a multi-model vLLM & Ollama fallback mesh.",
                        "citations": ["FEAT-452"],
                        "bone_collection": [],
                        "_candidate_pool": ["BKM-044"],
                    }
                ],
            }
        ],
    }


async def _call_import_handler(payload):
    """Invoke FoyerRouter.handle_paper_import offline with a mocked request."""
    request = MagicMock()
    request.json = AsyncMock(return_value=payload)
    with patch("src.v5.foyer.router.atomic_write_json") as mock_write:
        # handle_paper_import never touches `self`; object() is a pure type-seam dummy.
        response = await FoyerRouter.handle_paper_import(object(), request)  # type: ignore[arg-type]
    return response, mock_write


def _resp_body(response):
    """Decode the JSON payload of an aiohttp web.Response (no .json() in older aiohttp)."""
    return json.loads(response.text)


def _assert_nested(ast, section_idx, paragraph_idx, key):
    return ast["sections"][section_idx]["paragraphs"][paragraph_idx][key]


# ---------------------------------------------------------------------------
# Citation discovery (Phase 1 DISCOVER)
# ---------------------------------------------------------------------------
def test_detect_citations_all_formats_deduped():
    text = ("Shipped FEAT-181 alongside BKM-010; revisited FEAT-181 again. "
            "Published ARXIV:2401.12345 and doi:10.1000/xyz123. Also WIS-042.")
    found = detect_citations(text)
    assert found == ["FEAT-181", "BKM-010", "ARXIV:2401.12345", "doi:10.1000/xyz123", "WIS-042"]
    # deduplicated: FEAT-181 appears once


def test_detect_citations_empty_text():
    assert detect_citations("") == []
    assert detect_citations(None) == []


# ---------------------------------------------------------------------------
# Markdown import
# ---------------------------------------------------------------------------
def test_markdown_title_extraction_and_two_tier_roots():
    md = "# Staff Infrastructure Resume\n\n## Experience\n\nArchitected vLLM mesh.\n"
    ast = parse_markdown(md)
    assert ast["title"] == "Staff Infrastructure Resume"
    assert ast["bone_collection"] == []
    assert ast["_candidate_pool"] == []
    assert len(ast["sections"]) == 1
    assert ast["sections"][0]["heading"] == "Experience"


def test_markdown_hierarchical_section_parsing():
    md = (
        "# Title\n\n"
        "## Distributed AI\n\nFirst paragraph of AI section.\n\n"
        "### Model Mesh\n\nMesh paragraph.\n\n"
        "## LaTeX Compilation\n\nCompiler paragraph.\n"
    )
    ast = parse_markdown(md)
    assert ast["title"] == "Title"
    assert [s["heading"] for s in ast["sections"]] == [
        "Distributed AI", "Model Mesh", "LaTeX Compilation"
    ]
    # heading hierarchy is flattened but preserved via 'level' metadata
    assert [s["level"] for s in ast["sections"]] == [2, 3, 2]
    # each section owns its own paragraphs
    assert len(ast["sections"][0]["paragraphs"]) == 1
    assert ast["sections"][1]["paragraphs"][0]["text"] == "Mesh paragraph."
    # deterministic ids
    assert ast["sections"][0]["id"] == "sec-01"
    assert ast["sections"][1]["id"] == "sec-02"


def test_markdown_bullet_and_paragraph_typing():
    md = (
        "# Resume\n\n"
        "## Impact\n\n"
        "- Built FEAT-181 pipeline end-to-end.\n"
        "- Cut latency by 40%.\n\n"
        "Long-form paragraph covering architecture.\n"
    )
    ast = parse_markdown(md)
    pars = ast["sections"][0]["paragraphs"]
    assert [p["bullet_type"] for p in pars] == ["bullet", "bullet", "paragraph"]
    assert [p["text"] for p in pars][0] == "Built FEAT-181 pipeline end-to-end."


def test_markdown_preamble_section_before_first_heading():
    md = "Lead-in sentence before any heading.\n\n# Real Title\n\n## Body\n\nContent.\n"
    ast = parse_markdown(md)
    assert ast["title"] == "Real Title"
    assert ast["sections"][0]["heading"] == "Preamble"
    assert ast["sections"][0]["paragraphs"][0]["text"] == "Lead-in sentence before any heading."


# ---------------------------------------------------------------------------
# Plain text import
# ---------------------------------------------------------------------------
def test_plain_text_single_overview_section():
    text = "Paragraph one here.\n\nParagraph two here.\n"
    ast = parse_plain_text(text)
    assert ast["title"] == DEFAULT_TITLE
    assert len(ast["sections"]) == 1
    section = ast["sections"][0]
    assert section["heading"] == "Overview"
    assert section["id"] == "sec-01"
    assert [p["text"] for p in section["paragraphs"]] == ["Paragraph one here.", "Paragraph two here."]
    assert all(p["bullet_type"] == "paragraph" for p in section["paragraphs"])


def test_plain_text_bullet_detection():
    text = "- First bullet\n- Second bullet\n\nClosing paragraph.\n"
    ast = parse_plain_text(text)
    pars = ast["sections"][0]["paragraphs"]
    assert [p["bullet_type"] for p in pars] == ["bullet", "bullet", "paragraph"]


def test_parse_document_format_hint_plain():
    ast = parse_document("hello world", source_format="text")
    assert ast["sections"][0]["heading"] == "Overview"


# ---------------------------------------------------------------------------
# JSON import
# ---------------------------------------------------------------------------
def test_json_string_canonical_preserves_citations_and_discovers():
    doc = {
        "title": "Canonical Doc",
        "bone_collection": ["FEAT-181"],
        "_candidate_pool": [],
        "sections": [
            {
                "id": "sec-01",
                "heading": "Infra",
                "bone_collection": [],
                "_candidate_pool": [],
                "paragraphs": [
                    {
                        "id": "p-01",
                        "bullet_type": "bullet",
                        "text": "Operated the BKM-044 engine while citing FEAT-136.",
                        "citations": ["FEAT-452"],
                        "bone_collection": [],
                        "_candidate_pool": [],
                    }
                ],
            }
        ],
    }
    ast = parse_json_document(json.dumps(doc))
    # explicit citations preserved
    assert _assert_nested(ast, 0, 0, "citations") == ["FEAT-452"]
    # explicit root bone_collection preserved
    assert ast["bone_collection"] == ["FEAT-181"]
    # DISCOVER phase: new tokens merged into candidate pool
    assert _assert_nested(ast, 0, 0, "_candidate_pool") == ["BKM-044", "FEAT-136"]


def test_generic_json_object_conversion():
    generic = {
        "title": "Generic Profile",
        "Experience": "Ran the cluster for 5 years.",
        "Skills": ["Python", "Kubernetes", "vLLM"],
    }
    ast = parse_json_document(generic)
    assert ast["title"] == "Generic Profile"
    headings = [s["heading"] for s in ast["sections"]]
    assert headings == ["Experience", "Skills"]
    # string value -> paragraph entry
    assert ast["sections"][0]["paragraphs"][0]["bullet_type"] == "paragraph"
    # list value -> bullet entries
    skills = ast["sections"][1]["paragraphs"]
    assert [p["bullet_type"] for p in skills] == ["bullet", "bullet", "bullet"]


def test_json_malformed_raises():
    with pytest.raises(ValueError):
        parse_json_document("{not valid json!!")


def test_parse_document_autodetect_json_vs_text():
    json_ast = parse_document('{"title": "Auto", "sections": []}')
    assert json_ast["title"] == "Auto"
    text_ast = parse_document("no json here at all")
    assert text_ast["sections"][0]["heading"] == "Overview"


def test_parse_document_empty_content_raises():
    with pytest.raises(ValueError):
        parse_document("   ")


# ---------------------------------------------------------------------------
# Bone collection / candidate pool initialization (two-tier semantics)
# ---------------------------------------------------------------------------
def test_import_initializes_bone_empty_candidate_populated():
    md = (
        "# Ops Resume\n\n"
        "## Platform\n\n"
        "Ran BKM-010 load tests and shipped FEAT-181.\n\n"
        "- Landed WIS-042 guidance in the mesh.\n"
    )
    ast = parse_markdown(md)
    # bone_collection is empty at EVERY tier on import (curation is a later phase)
    assert ast["bone_collection"] == []
    assert ast["sections"][0]["bone_collection"] == []
    assert all(p["bone_collection"] == [] for p in ast["sections"][0]["paragraphs"])
    # discovered citations populate the candidate pools at the tiers where they appear
    assert "BKM-010" in ast["sections"][0]["paragraphs"][0]["_candidate_pool"]
    assert "FEAT-181" in ast["sections"][0]["paragraphs"][0]["_candidate_pool"]
    assert ast["sections"][0]["paragraphs"][1]["_candidate_pool"] == ["WIS-042"]


def test_explicit_bone_collection_survives_normalization():
    canonical = _valid_ast()
    ast = parse_json_document(canonical)
    assert ast["bone_collection"] == ["FEAT-181"]
    assert ast["sections"][0]["bone_collection"] == ["WIS-108"]
    # bone_collection untouched by the import pipeline
    assert _assert_nested(ast, 0, 0, "bone_collection") == []


# ---------------------------------------------------------------------------
# Strict schema validation — error handling for invalid documents
# ---------------------------------------------------------------------------
def test_validate_valid_ast_passes():
    passed, errors = validate_paper_dict(_valid_ast(), source_name="paper_test")
    assert passed is True
    assert errors == []


def test_validate_missing_title():
    bad = _valid_ast()
    del bad["title"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("title" in e for e in errors)


def test_validate_missing_sections():
    bad = {"title": "No Sections", "bone_collection": [], "_candidate_pool": []}
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("sections" in e for e in errors)


def test_validate_root_two_tier_invariant():
    bad = _valid_ast()
    del bad["_candidate_pool"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("_candidate_pool" in e and "two-tier" in e for e in errors)


def test_validate_section_two_tier_invariant():
    bad = _valid_ast()
    del bad["sections"][0]["bone_collection"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("bone_collection" in e and "two-tier" in e for e in errors)


def test_validate_paragraph_two_tier_invariant():
    bad = _valid_ast()
    del bad["sections"][0]["paragraphs"][0]["_candidate_pool"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("_candidate_pool" in e and "two-tier" in e for e in errors)


def test_validate_bone_collection_not_list():
    bad = _valid_ast()
    bad["bone_collection"] = "FEAT-181"  # must be a list
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("must be a list" in e for e in errors)


def test_validate_invalid_citation_syntax():
    bad = _valid_ast()
    bad["sections"][0]["paragraphs"][0]["citations"] = ["NOT-A-CITATION"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("valid citation ID" in e for e in errors)


def test_validate_empty_candidate_pool_entry():
    bad = _valid_ast()
    bad["_candidate_pool"] = [""]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("non-empty string" in e for e in errors)


def test_validate_duplicate_ids():
    bad = _valid_ast()
    bad["sections"].append(json.loads(json.dumps(bad["sections"][0])))  # duplicate sec-01 + p-01
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("duplicate section id" in e for e in errors)
    assert any("duplicate paragraph id" in e for e in errors)


def test_validate_empty_paragraph_text():
    bad = _valid_ast()
    bad["sections"][0]["paragraphs"][0]["text"] = "   "
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("non-empty 'text'" in e for e in errors)


def test_validate_missing_heading():
    bad = _valid_ast()
    del bad["sections"][0]["heading"]
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("heading" in e for e in errors)


def test_validate_invalid_bullet_type():
    bad = _valid_ast()
    bad["sections"][0]["paragraphs"][0]["bullet_type"] = "headline"
    passed, errors = validate_paper_dict(bad)
    assert passed is False
    assert any("bullet_type" in e for e in errors)


def test_validate_non_object_root():
    passed, errors = validate_paper_dict(["not", "a", "dict"])
    assert passed is False
    assert any("must be a JSON object" in e for e in errors)


def test_validate_unknown_keys_ignored():
    good = _valid_ast()
    good["subtitle"] = "allowed metadata"
    good["sections"][0]["level"] = 2
    passed, errors = validate_paper_dict(good)
    assert passed is True


# ---------------------------------------------------------------------------
# POST /paper/import handler (offline)
# ---------------------------------------------------------------------------
def test_route_registered():
    def path_of(route):
        resource = getattr(route, "resource", None)
        return getattr(resource, "canonical", None) if resource else None

    routes = FoyerRouter(disable_ear=True).app.router.routes()
    paths = {(route.method, path_of(route)) for route in routes}
    assert ("POST", "/paper/import") in paths
    assert ("POST", "/attendant/paper/import") in paths


@pytest.mark.asyncio
async def test_handle_paper_import_markdown_success():
    response, mock_write = await _call_import_handler({
        "title": "Ops Resume",
        "content": "# Ops Resume\n\n## Platform\n\nRan BKM-010 tests and shipped FEAT-181.\n",
    })
    assert response.status == 200
    body = _resp_body(response)
    assert body["status"] == "success"
    assert body["title"] == "Ops Resume"
    ast = body["ast"]
    assert ast["bone_collection"] == []
    assert ast["sections"][0]["heading"] == "Platform"
    assert ast["sections"][0]["paragraphs"][0]["_candidate_pool"] == ["BKM-010", "FEAT-181"]
    assert body["stats"]["sections"] == 1
    assert body["stats"]["candidate_pool"] == 2
    assert body["file"].endswith(".json")
    # the AST was atomically persisted (mock intercepts every disk write)
    assert mock_write.called


@pytest.mark.asyncio
async def test_handle_paper_import_json_success():
    payload = {"content": json.dumps({"title": "JSON Doc", "scope": "Ran WIS-042 pipelines."}), "format": "json"}
    response, _ = await _call_import_handler(payload)
    assert response.status == 200
    body = _resp_body(response)
    assert body["ast"]["title"] == "JSON Doc"
    assert body["ast"]["sections"][0]["heading"] == "scope"


@pytest.mark.asyncio
async def test_handle_paper_import_canonical_document_direct():
    response, _ = await _call_import_handler(_valid_ast())
    assert response.status == 200
    body = _resp_body(response)
    assert body["ast"]["bone_collection"] == ["FEAT-181"]
    assert body["stats"]["paragraphs"] == 1


@pytest.mark.asyncio
async def test_handle_paper_import_missing_content_400():
    response, _ = await _call_import_handler({"title": "Nothing Else"})
    assert response.status == 400
    body = _resp_body(response)
    assert "Missing document content" in body["message"]


@pytest.mark.asyncio
async def test_handle_paper_import_malformed_json_400():
    response, _ = await _call_import_handler({"content": "{broken json", "format": "json"})
    assert response.status == 400
    body = _resp_body(response)
    assert "could not be parsed" in body["message"]


@pytest.mark.asyncio
async def test_handle_paper_import_invalid_schema_400():
    # Only a title -> generic JSON conversion yields zero sections -> validator rejects
    response, _ = await _call_import_handler({"content": {"title": "Only Title"}})
    assert response.status == 400
    body = _resp_body(response)
    assert "failed two-tier AST schema validation" in body["message"]
    assert any("sections" in e for e in body["errors"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
