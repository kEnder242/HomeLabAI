"""
[SPR-82.3] Target Objective & JD Matching Engine — comprehensive unit suite.
=============================================================================
Verifies:
  • cosine similarity scoring math (identical / orthogonal / negated / scaled /
    zero-norm / empty vectors);
  • Waterline action tagging: KEEP (>= 0.70), REVIEW (0.50 <= score < 0.70),
    PRUNE (< 0.50), including exact-threshold boundary filtering through the
    full evaluation pipeline;
  • evaluate_ast_objective() per-bullet scoring across every section / paragraph
    / bullet of the paper AST (the paper_dna_<slug> node set) with order
    preservation, slug derivation, and aggregate keep/review/prune stats;
  • recommended chip attachments from the global DNA collections (feature_dna /
    behavioral_dna / long_term_wisdom) merged via query_hybrid_dna, plus
    graceful degradation to [] when ChromaDB is unreachable (BKM-055);
  • error handling for missing papers (PaperNotFoundError), empty objectives,
    and invalid AST inputs;
  • POST /paper/evaluate_objective handler behavior (200 / 400 / 404 / 500, text
    alias, AST passthrough) and route registration.

Hermetic: no live ChromaDB, no daemon, and no onnx/torch model is ever loaded —
every embedding is injected as a deterministic fake and the DNA query layer is
patched. Requires only pytest + the repo's own modules.
"""
import json
import math
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

HOME_LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ~/Dev_Lab/HomeLabAI
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(HOME_LAB)), "Portfolio_Dev", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from curator.objective_evaluator import (  # noqa: E402
    DEFAULT_PER_COLLECTION_K,
    GLOBAL_COLLECTIONS,
    KEEP_THRESHOLD,
    REVIEW_THRESHOLD,
    PaperNotFoundError,
    cosine_similarity,
    default_embed,
    evaluate_ast_objective,
    evaluate_objective,
    get_embedding_function,
    tag_score,
)
from src.v5.foyer.router import FoyerRouter  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic fake embedder (never touches onnx/torch)
# ---------------------------------------------------------------------------
class DictEmbed:
    """Deterministic fake embedder: maps exact text -> fixed vector."""

    def __init__(self, vectors):
        self.vectors = dict(vectors)

    def __call__(self, texts):
        return np.asarray([self.vectors[t] for t in texts], dtype=np.float64)


# Unit vectors along canonical directions (all exact-compute friendly).
V_IDENT = np.array([1.0, 0.0, 0.0])          # cosine 1.00 vs objective
V_KEEP8 = np.array([0.8, 0.6, 0.0])          # cosine 0.80 (unit length)
V_KEEP7 = np.array([0.7, math.sqrt(0.51), 0.0])   # cosine 0.70 exactly
V_REVIEW6 = np.array([0.6, 0.8, 0.0])        # cosine 0.60 (unit length)
V_REVIEW5 = np.array([0.5, math.sqrt(0.75), 0.0])  # cosine 0.50 exactly
V_PRUNE4 = np.array([0.4, math.sqrt(0.84), 0.0])   # cosine 0.40 (unit length)
V_ZERO = np.array([0.0, 1.0, 0.0])           # cosine 0.00

OBJECTIVE = "Senior AI Infrastructure Engineer"


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------
def _ast(**overrides):
    """A canonical two-tier AST (valid per validate_paper_schema.py)."""
    ast = {
        "id": "PAPER-001",
        "title": "Staff Infrastructure & AI Platforms Resume",
        "sections": [
            {
                "id": "sec-01",
                "heading": "Distributed AI Infrastructure",
                "paragraphs": [
                    {
                        "id": "p-01",
                        "bullet_type": "bullet",
                        "text": "Built the BKM-010 fallback mesh end-to-end.",
                    },
                    {
                        "id": "p-02",
                        "bullet_type": "paragraph",
                        "text": "Operated the vLLM and Ollama dual-engine stack.",
                    },
                ],
            },
            {
                "id": "sec-02",
                "heading": "Deterministic LaTeX Compilation",
                "paragraphs": [
                    {
                        "id": "p-03",
                        "bullet_type": "bullet",
                        "text": "Compiled zero-dependency PDFs from cached bones.",
                    },
                ],
            },
        ],
    }
    ast.update(overrides)
    return ast


# Deterministic per-node vector map for the fixture AST above.
BULK_VECTORS = {
    OBJECTIVE: V_IDENT,
    "Distributed AI Infrastructure": V_IDENT,                              # 1.00 KEEP
    "Built the BKM-010 fallback mesh end-to-end.": V_REVIEW6,              # 0.60 REVIEW
    "Operated the vLLM and Ollama dual-engine stack.": V_ZERO,             # 0.00 PRUNE
    "Deterministic LaTeX Compilation": V_KEEP8,                            # 0.80 KEEP
    "Compiled zero-dependency PDFs from cached bones.": V_REVIEW6,         # 0.60 REVIEW
}
EXPECTED_BULLET_COUNT = 5  # 2 sections + 3 paragraphs/bullets (doc root skipped)


def _resp_body(response):
    """Decode the JSON payload of an aiohttp web.Response."""
    return json.loads(response.text)


async def _call_eval_handler(payload):
    """Invoke FoyerRouter.handle_paper_evaluate_objective offline with a mocked request."""
    request = MagicMock()
    request.json = AsyncMock(return_value=payload)
    return await FoyerRouter.handle_paper_evaluate_objective(object(), request)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Scoring math
# ---------------------------------------------------------------------------
def test_cosine_similarity_math():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0, 0], [-1, 0, 0]) == pytest.approx(-1.0)
    assert cosine_similarity([1, 0, 0], [0.6, 0.8, 0]) == pytest.approx(0.6)
    assert cosine_similarity([2, 0, 0], [6, 0, 0]) == pytest.approx(1.0)  # scale-invariant
    assert cosine_similarity([0, 0, 0], [1, 0, 0]) == 0.0  # zero norm -> 0.0
    assert cosine_similarity([1, 2], []) == 0.0            # empty vector -> 0.0


# ---------------------------------------------------------------------------
# Waterline action tags (pruning thresholds)
# ---------------------------------------------------------------------------
def test_tag_score_thresholds():
    assert tag_score(1.0) == "KEEP"
    assert tag_score(KEEP_THRESHOLD) == "KEEP"      # 0.70 inclusive
    assert tag_score(0.85) == "KEEP"
    assert tag_score(0.6999) == "REVIEW"
    assert tag_score(REVIEW_THRESHOLD) == "REVIEW"  # 0.50 inclusive
    assert tag_score(0.55) == "REVIEW"
    assert tag_score(0.4999) == "PRUNE"
    assert tag_score(0.0) == "PRUNE"
    assert tag_score(-0.1) == "PRUNE"


def test_threshold_constants_match_spec():
    assert KEEP_THRESHOLD == 0.70
    assert REVIEW_THRESHOLD == 0.50


# ---------------------------------------------------------------------------
# evaluate_ast_objective() — full scoring pipeline over paper_dna_<slug> nodes
# ---------------------------------------------------------------------------
def test_evaluate_ast_objective_full_scoring_pipeline():
    result = evaluate_ast_objective(_ast(), OBJECTIVE, slug="resume", embed=DictEmbed(BULK_VECTORS))
    assert result["objective"] == OBJECTIVE
    assert result["slug"] == "resume"
    assert result["bullet_count"] == EXPECTED_BULLET_COUNT
    # insertion order preserved; doc root skipped; sections + bullets all scored
    assert [b["node_id"] for b in result["bullets"]] == [
        "resume:sec-01", "resume:sec-01:p-01", "resume:sec-01:p-02",
        "resume:sec-02", "resume:sec-02:p-03",
    ]
    bullets = {b["node_id"]: b for b in result["bullets"]}
    assert bullets["resume:sec-01"]["score"] == 1.0
    assert bullets["resume:sec-01"]["action"] == "KEEP"
    assert bullets["resume:sec-01"]["node_type"] == "section"
    assert bullets["resume:sec-01:p-01"]["score"] == 0.6
    assert bullets["resume:sec-01:p-01"]["action"] == "REVIEW"
    assert bullets["resume:sec-01:p-01"]["node_type"] == "bullet"
    assert bullets["resume:sec-01:p-02"]["score"] == 0.0
    assert bullets["resume:sec-01:p-02"]["action"] == "PRUNE"
    assert bullets["resume:sec-02"]["score"] == 0.8
    assert bullets["resume:sec-02"]["action"] == "KEEP"
    assert result["stats"] == {"keep": 2, "review": 2, "prune": 1}
    assert result["thresholds"] == {"keep": 0.70, "review": 0.50}


def test_evaluate_ast_objective_pruning_threshold_filtering():
    """Exact 0.70 / 0.50 / 0.40 boundary bullets tag KEEP / REVIEW / PRUNE."""
    boundary_ast = {
        "title": "Boundary Paper",
        "sections": [
            {"id": "sec-a", "heading": "Exact KEEP Threshold", "paragraphs": [
                {"id": "p-a", "bullet_type": "bullet", "text": "Hits 0.70 exactly."}]},
            {"id": "sec-b", "heading": "Exact REVIEW Threshold", "paragraphs": [
                {"id": "p-b", "bullet_type": "bullet", "text": "Hits 0.50 exactly."}]},
            {"id": "sec-c", "heading": "Below Review Threshold", "paragraphs": [
                {"id": "p-c", "bullet_type": "bullet", "text": "Scores 0.40."}]},
        ],
    }
    vectors = {
        OBJECTIVE: V_IDENT,
        "Exact KEEP Threshold": V_KEEP7,
        "Hits 0.70 exactly.": V_KEEP7,
        "Exact REVIEW Threshold": V_REVIEW5,
        "Hits 0.50 exactly.": V_REVIEW5,
        "Below Review Threshold": V_PRUNE4,
        "Scores 0.40.": V_PRUNE4,
    }
    result = evaluate_ast_objective(boundary_ast, OBJECTIVE, slug="boundary", embed=DictEmbed(vectors))
    actions = {b["node_id"]: b["action"] for b in result["bullets"]}
    assert actions == {
        "boundary:sec-a": "KEEP",
        "boundary:sec-a:p-a": "KEEP",
        "boundary:sec-b": "REVIEW",
        "boundary:sec-b:p-b": "REVIEW",
        "boundary:sec-c": "PRUNE",
        "boundary:sec-c:p-c": "PRUNE",
    }
    assert result["stats"] == {"keep": 2, "review": 2, "prune": 2}


def test_evaluate_ast_objective_slug_defaults_from_title():
    result = evaluate_ast_objective(_ast(), OBJECTIVE, embed=DictEmbed(BULK_VECTORS))
    assert result["slug"] == "staff-infrastructure-ai-platforms-resume"
    assert result["bullets"][0]["node_id"].startswith("staff-infrastructure-ai-platforms-resume:")


def test_evaluate_ast_objective_scores_are_rounded_four_decimals():
    result = evaluate_ast_objective(_ast(), OBJECTIVE, slug="resume", embed=DictEmbed(BULK_VECTORS))
    for bullet in result["bullets"]:
        assert isinstance(bullet["score"], float)
        assert round(bullet["score"], 4) == bullet["score"]


# ---------------------------------------------------------------------------
# Recommended chip attachments (global DNA collections)
# ---------------------------------------------------------------------------
def test_evaluate_ast_objective_chip_attachments_query_global_collections():
    fake_chips = [
        {"collection": "feature_dna", "id": "FEAT-181", "node_id": "FEAT-181",
         "node_type": "", "heading": "", "slug": "", "document": "FEAT-181",
         "distance": 0.08, "score": 0.92},
        {"collection": "behavioral_dna", "id": "BKM-044", "node_id": "BKM-044",
         "node_type": "", "heading": "", "slug": "", "document": "BKM-044",
         "distance": 0.13, "score": 0.87},
        {"collection": "long_term_wisdom", "id": "WIS-042", "node_id": "WIS-042",
         "node_type": "", "heading": "", "slug": "", "document": "WIS-042",
         "distance": 0.36, "score": 0.64},
    ]
    with patch("curator.objective_evaluator.query_hybrid_dna", return_value=fake_chips) as mock_query:
        result = evaluate_ast_objective(_ast(), OBJECTIVE, slug="resume",
                                        embed=DictEmbed(BULK_VECTORS), top_k=2)
    assert result["suggested_chips"] == fake_chips  # unchanged: merged/ranked upstream
    mock_query.assert_called_once_with(
        OBJECTIVE,
        slug=None,
        collections=GLOBAL_COLLECTIONS,
        top_k=2,
        per_collection_k=DEFAULT_PER_COLLECTION_K,
    )


def test_evaluate_ast_objective_chips_offline_degrade_gracefully():
    """Unreachable ChromaDB must never block bullet scoring (BKM-055)."""
    with patch("curator.objective_evaluator.query_hybrid_dna",
               side_effect=RuntimeError("chroma down")):
        result = evaluate_ast_objective(_ast(), OBJECTIVE, slug="resume", embed=DictEmbed(BULK_VECTORS))
    assert result["suggested_chips"] == []
    assert result["bullet_count"] == EXPECTED_BULLET_COUNT
    assert result["stats"] == {"keep": 2, "review": 2, "prune": 1}


def test_evaluate_ast_objective_accepts_custom_collections():
    with patch("curator.objective_evaluator.query_hybrid_dna", return_value=[]) as mock_query:
        evaluate_ast_objective(_ast(), OBJECTIVE, slug="resume",
                               embed=DictEmbed(BULK_VECTORS), collections=["feature_dna"])
    _args, kwargs = mock_query.call_args
    assert kwargs["collections"] == ("feature_dna",)


# ---------------------------------------------------------------------------
# Invalid inputs
# ---------------------------------------------------------------------------
def test_evaluate_ast_objective_invalid_inputs():
    with pytest.raises(ValueError):
        evaluate_ast_objective({"title": "missing sections key"}, OBJECTIVE, slug="broken")
    with pytest.raises(ValueError):
        evaluate_ast_objective(_ast(), "   ", slug="resume")


# ---------------------------------------------------------------------------
# evaluate_objective() — paper source resolution
# ---------------------------------------------------------------------------
def test_evaluate_objective_from_ast_dict():
    result = evaluate_objective(OBJECTIVE, ast=_ast(), slug="resume", embed=DictEmbed(BULK_VECTORS))
    assert result["slug"] == "resume"
    assert result["bullet_count"] == EXPECTED_BULLET_COUNT
    assert result["stats"] == {"keep": 2, "review": 2, "prune": 1}


def test_evaluate_objective_from_slug_resolves_disk_ast(tmp_path):
    (tmp_path / "paper_ops-resume.json").write_text(json.dumps(_ast()), encoding="utf-8")
    with patch("curator.objective_evaluator.PAPERS_DIR", str(tmp_path)):
        result = evaluate_objective(OBJECTIVE, slug="ops-resume", embed=DictEmbed(BULK_VECTORS))
    assert result["slug"] == "ops-resume"
    assert result["bullet_count"] == EXPECTED_BULLET_COUNT


def test_evaluate_objective_from_paper_path(tmp_path):
    paper_file = tmp_path / "paper_jitc_intuition.json"
    paper_file.write_text(json.dumps(_ast()), encoding="utf-8")
    result = evaluate_objective(OBJECTIVE, paper_path=str(paper_file), embed=DictEmbed(BULK_VECTORS))
    assert result["slug"] == "jitc-intuition"
    assert result["stats"] == {"keep": 2, "review": 2, "prune": 1}


def test_evaluate_objective_missing_paper_raises_paper_not_found(tmp_path):
    with patch("curator.objective_evaluator.PAPERS_DIR", str(tmp_path)):
        with pytest.raises(PaperNotFoundError) as exc:
            evaluate_objective(OBJECTIVE, slug="never-imported")
    message = str(exc.value)
    assert "never-imported" in message
    assert "paper_never-imported.json" in message
    assert isinstance(exc.value, ValueError)  # compatible with generic callers


def test_evaluate_objective_empty_objective_errors():
    with pytest.raises(ValueError):
        evaluate_objective("   ")
    with pytest.raises(ValueError):
        evaluate_objective(None)  # type: ignore[arg-type]


def test_evaluate_objective_no_paper_source_errors():
    with pytest.raises(ValueError, match="Provide a paper source"):
        evaluate_objective(OBJECTIVE)


# ---------------------------------------------------------------------------
# Embedding function (BKM-054: strictly zero in-process torch)
# ---------------------------------------------------------------------------
def test_get_embedding_function_uses_onnx_minilm_not_torch():
    with patch("chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2", return_value="onnx-ef") as mock_ef:
        assert get_embedding_function() == "onnx-ef"
        mock_ef.assert_called_once_with()
    # default_embed routes through the ONNX embedding function
    with patch("curator.objective_evaluator.get_embedding_function") as mock_get:
        mock_get.return_value = MagicMock(return_value=[[0.5, 0.5], [1.0, 0.0]])
        out = default_embed(["a", "b"])
        assert out.shape == (2, 2)
        mock_get.assert_called_once_with()
    # module source must never import torch nor the torch-backed SentenceTransformer path
    module_path = os.path.join(HOME_LAB, "src", "curator", "objective_evaluator.py")
    with open(module_path, encoding="utf-8") as fh:
        module_src = fh.read()
    assert "import torch" not in module_src
    assert "from torch" not in module_src
    assert "SentenceTransformerEmbeddingFunction" not in module_src


# ---------------------------------------------------------------------------
# POST /paper/evaluate_objective handler
# ---------------------------------------------------------------------------
def test_evaluate_objective_route_registered():
    def path_of(route):
        resource = getattr(route, "resource", None)
        return getattr(resource, "canonical", None) if resource else None

    routes = FoyerRouter(disable_ear=True).app.router.routes()
    paths = {(route.method, path_of(route)) for route in routes}
    assert ("POST", "/paper/evaluate_objective") in paths
    assert ("POST", "/attendant/paper/evaluate_objective") in paths


@pytest.mark.asyncio
async def test_handle_paper_evaluate_objective_success():
    fake_result = {
        "objective": OBJECTIVE,
        "slug": "resume",
        "bullet_count": 2,
        "bullets": [
            {"node_id": "resume:sec-01", "node_type": "section",
             "heading": "Distributed AI Infrastructure", "text": "Distributed AI Infrastructure",
             "score": 0.98, "action": "KEEP"},
            {"node_id": "resume:sec-01:p-01", "node_type": "bullet",
             "heading": "Distributed AI Infrastructure",
             "text": "Built the BKM-010 fallback mesh end-to-end.",
             "score": 0.61, "action": "REVIEW"},
        ],
        "stats": {"keep": 1, "review": 1, "prune": 0},
        "suggested_chips": [{"collection": "feature_dna", "id": "FEAT-181", "score": 0.9}],
        "thresholds": {"keep": 0.70, "review": 0.50},
    }
    with patch("curator.objective_evaluator.evaluate_objective", return_value=fake_result) as mock_eval:
        response = await _call_eval_handler({
            "objective": OBJECTIVE, "slug": "resume", "top_k": 3,
        })
    assert response.status == 200
    body = _resp_body(response)
    assert body["status"] == "success"
    assert body["objective"] == OBJECTIVE
    assert body["slug"] == "resume"
    assert body["bullet_count"] == 2
    assert body["bullets"][0]["action"] == "KEEP"
    assert body["stats"] == {"keep": 1, "review": 1, "prune": 0}
    assert body["suggested_chips"][0]["id"] == "FEAT-181"
    assert "timestamp" in body
    mock_eval.assert_called_once_with(
        OBJECTIVE, slug="resume", ast=None, top_k=3, collections=None,
    )


@pytest.mark.asyncio
async def test_handle_paper_evaluate_objective_accepts_text_alias_and_ast():
    ast = _ast()
    stub = {
        "objective": "JD brief", "slug": "resume", "bullet_count": 0, "bullets": [],
        "stats": {"keep": 0, "review": 0, "prune": 0}, "suggested_chips": [],
        "thresholds": {"keep": 0.70, "review": 0.50},
    }
    with patch("curator.objective_evaluator.evaluate_objective", return_value=stub) as mock_eval:
        response = await _call_eval_handler({"text": "JD brief", "slug": "resume", "ast": ast})
    assert response.status == 200
    assert _resp_body(response)["status"] == "success"
    _args, kwargs = mock_eval.call_args
    assert _args[0] == "JD brief"
    assert kwargs["ast"] == ast
    assert kwargs["slug"] == "resume"


@pytest.mark.asyncio
async def test_handle_paper_evaluate_objective_missing_objective_400():
    response = await _call_eval_handler({"slug": "resume"})
    assert response.status == 400
    assert "Missing target objective" in _resp_body(response)["message"]


@pytest.mark.asyncio
async def test_handle_paper_evaluate_objective_missing_paper_404():
    with patch("curator.objective_evaluator.evaluate_objective",
               side_effect=PaperNotFoundError(
                   "No paper found for slug 'ghost' (expected .../paper_ghost.json)")):
        response = await _call_eval_handler({"objective": "JD", "slug": "ghost"})
    assert response.status == 404
    assert "No paper found" in _resp_body(response)["message"]


@pytest.mark.asyncio
async def test_handle_paper_evaluate_objective_error_500():
    with patch("curator.objective_evaluator.evaluate_objective",
               side_effect=RuntimeError("boom")):
        response = await _call_eval_handler({"objective": "JD", "slug": "resume"})
    assert response.status == 500
    assert "boom" in _resp_body(response)["message"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
