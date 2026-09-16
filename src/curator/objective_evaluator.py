#!/usr/bin/env python3
"""[SPR-82.3] Target Objective & JD Matching Engine — semantic alignment scoring.

Implements Story 82.3 of SPR-82.0 (Generic Scoped Document Ingestion, Decoupled
Two-Tier AST Palette & Anti-Embellishment Combinatorial Studio), Phase 2
CURATE semantics:

* **Requirement embedding** — the target objective / Job Description (JD) text
  is embedded with ``chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2``
  (ONNX runtime — strictly zero in-process torch per BKM-054).
* **Per-bullet alignment scoring** — cosine similarity (0.00 – 1.00) between
  the objective vector and every section / paragraph / bullet of the paper's
  two-tier AST (the exact node set synced into ``paper_dna_<slug>`` by
  ``sync_paper_dna.iter_paper_nodes``), with deterministic Waterline action
  tags: ``KEEP`` (score >= 0.70), ``REVIEW`` (0.50 <= score < 0.70), ``PRUNE``
  (score < 0.50).
* **Recommended chip attachments** — the objective is queried against the
  global DNA collections (``feature_dna``, ``behavioral_dna``,
  ``long_term_wisdom``) via ``sync_paper_dna.query_hybrid_dna`` to surface
  candidate citations/chips to attach (Phase 1 DISCOVER semantics), merged,
  de-duplicated by (collection, id), and ranked by similarity score.
* **Graceful degradation** — per BKM-055, an unreachable ChromaDB or missing
  global collection yields empty ``suggested_chips`` and never blocks bullet
  scoring; a paper slug that resolves to no imported AST raises
  :class:`PaperNotFoundError` (mapped to HTTP 404 by the foyer router).

The paper AST is the deterministic source of the ``paper_dna_<slug>`` node set
(:func:`evaluate_objective` resolves a ``slug`` to the persisted import at
``PAPERS_DIR/paper_<slug>.json``), so scoring is reproducible offline without
round-tripping embedded collections.
"""

import logging
import os

import numpy as np
from chromadb.utils import embedding_functions

from curator.sync_paper_dna import (
    GLOBAL_COLLECTIONS,
    iter_paper_nodes,
    load_paper_ast,
    query_hybrid_dna,
    slugify,
)

# Config ---------------------------------------------------------------------
PAPERS_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/papers")
DEFAULT_TOP_K = 5
DEFAULT_PER_COLLECTION_K = 5

# Waterline thresholds (the anti-embellishment action tags)
KEEP_THRESHOLD = 0.70
REVIEW_THRESHOLD = 0.50

# BKM-054: ONNX MiniLM — strictly zero in-process torch.
EMBEDDING_MODEL = "onnx:all-MiniLM-L6-v2"

logger = logging.getLogger("objective_evaluator")


class PaperNotFoundError(ValueError):
    """Raised when a paper ``slug`` resolves to no imported paper AST on disk."""


# ----------------------------------------------------------------------------
# Embedding (BKM-054: ONNX runtime only — no in-process torch)
# ----------------------------------------------------------------------------
def get_embedding_function():
    """Return the ONNX MiniLM embedding function (strictly zero in-process torch)."""
    return embedding_functions.ONNXMiniLM_L6_V2()


def default_embed(texts):
    """Embed a list of texts via the ONNX embedding function -> (n, d) float64 array."""
    ef = get_embedding_function()
    return np.asarray(ef(list(texts)), dtype=np.float64)


# ----------------------------------------------------------------------------
# Scoring primitives
# ----------------------------------------------------------------------------
def cosine_similarity(vec_a, vec_b):
    """Cosine similarity between two vectors; 0.0 for empty or zero-norm inputs."""
    a = np.asarray(vec_a, dtype=np.float64).flatten()
    b = np.asarray(vec_b, dtype=np.float64).flatten()
    if a.size == 0 or b.size == 0:
        return 0.0
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def tag_score(score):
    """Map a cosine score to the deterministic Waterline action tag.

    ``KEEP`` for score >= 0.70, ``REVIEW`` for 0.50 <= score < 0.70,
    ``PRUNE`` for score < 0.50.
    """
    if score >= KEEP_THRESHOLD:
        return "KEEP"
    if score >= REVIEW_THRESHOLD:
        return "REVIEW"
    return "PRUNE"


# ----------------------------------------------------------------------------
# Target iteration (the paper_dna_<slug> node set)
# ----------------------------------------------------------------------------
def iter_objective_targets(ast, slug):
    """Yield every scoreable paper DNA target: sections, paragraphs, bullets.

    The document root node carries no requirement-scored text and is skipped —
    this is exactly the node set ``sync_paper_dna`` chunked into
    ``paper_dna_<slug>`` (minus the doc root).
    """
    for node in iter_paper_nodes(ast, slug):
        if node["node_type"] == "doc":
            continue
        yield node


# ----------------------------------------------------------------------------
# Core evaluation
# ----------------------------------------------------------------------------
def evaluate_ast_objective(ast, objective_text, slug=None, embed=None, top_k=DEFAULT_TOP_K,
                           collections=GLOBAL_COLLECTIONS, per_collection_k=DEFAULT_PER_COLLECTION_K):
    """[SPR-82.3] Score every section/paragraph/bullet of a paper AST against an objective.

    Embeds the target objective and every AST target node in a single batch,
    scores each with cosine similarity (rounded to 4 decimals), and tags the
    bullet with the deterministic Waterline action (KEEP / REVIEW / PRUNE).
    Also queries the global DNA collections for recommended chip attachments
    (merged, de-duplicated, ranked, truncated to ``top_k``). Unreachable
    ChromaDB or missing global collections degrade to empty ``suggested_chips``
    (BKM-055) without blocking scoring.

    ``embed`` overrides the embedder (signature ``list[str] -> (n, d) float
    array``); it defaults to the ONNX MiniLM embedder. ``slug`` defaults to the
    AST title. Returns the full evaluation payload: objective / slug /
    bullets / stats / suggested_chips / thresholds.
    """
    resolved_ast, _ = load_paper_ast(ast)
    objective = str(objective_text or "").strip()
    if not objective:
        raise ValueError("objective_text must be a non-empty string")
    resolved_slug = slugify(slug or resolved_ast.get("title") or "imported")
    collections = tuple(collections) if collections else GLOBAL_COLLECTIONS
    try:
        top_k = max(1, int(top_k))
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    try:
        per_collection_k = max(1, int(per_collection_k))
    except (TypeError, ValueError):
        per_collection_k = DEFAULT_PER_COLLECTION_K

    targets = list(iter_objective_targets(resolved_ast, resolved_slug))
    embedder = embed or default_embed
    batch = [objective] + [node["text"] for node in targets]
    vectors = np.asarray(embedder(batch), dtype=np.float64)
    objective_vec = vectors[0]

    bullets = []
    for i, node in enumerate(targets):
        score = round(cosine_similarity(objective_vec, vectors[i + 1]), 4)
        bullets.append({
            "node_id": node["node_id"],
            "node_type": node["node_type"],
            "heading": node["heading"],
            "text": node["text"],
            "score": score,
            "action": tag_score(score),
        })

    try:
        suggested_chips = query_hybrid_dna(
            objective,
            slug=None,
            collections=collections,
            top_k=top_k,
            per_collection_k=per_collection_k,
        )
    except Exception as e:
        logger.warning("[objective_evaluator] chip attachment query degraded: %s", e)
        suggested_chips = []

    return {
        "objective": objective,
        "slug": resolved_slug,
        "bullet_count": len(bullets),
        "bullets": bullets,
        "stats": {
            "keep": sum(1 for b in bullets if b["action"] == "KEEP"),
            "review": sum(1 for b in bullets if b["action"] == "REVIEW"),
            "prune": sum(1 for b in bullets if b["action"] == "PRUNE"),
        },
        "suggested_chips": suggested_chips,
        "thresholds": {"keep": KEEP_THRESHOLD, "review": REVIEW_THRESHOLD},
    }


def evaluate_objective(objective_text, ast=None, slug=None, paper_path=None,
                       top_k=DEFAULT_TOP_K, collections=GLOBAL_COLLECTIONS,
                       per_collection_k=DEFAULT_PER_COLLECTION_K, embed=None):
    """[SPR-82.3] Top-level target-objective / JD evaluation entry point.

    Resolves the paper AST from one of:

    * ``ast`` — an explicit canonical two-tier AST dict (used directly);
    * ``slug`` — loads ``PAPERS_DIR/paper_<slug>.json``, the AST mirrored by
      the ``paper_dna_<slug>`` collection (raises :class:`PaperNotFoundError`
      when the paper has not been imported);
    * ``paper_path`` — a path to a paper AST JSON file (slug from the stem).

    Raises ``ValueError`` for an empty objective or when no paper source is
    given, and delegates scoring to :func:`evaluate_ast_objective`.
    """
    objective = str(objective_text or "").strip()
    if not objective:
        raise ValueError("objective_text must be a non-empty string")

    if ast is not None:
        resolved_ast, _ = load_paper_ast(ast)
        resolved_slug = slugify(slug or resolved_ast.get("title") or "imported")
    elif slug:
        resolved_slug = slugify(slug)
        path = paper_path or os.path.join(PAPERS_DIR, f"paper_{resolved_slug}.json")
        if not os.path.exists(path):
            raise PaperNotFoundError(
                f"No paper found for slug '{slug}' (expected {path}). "
                "Import the document via POST /paper/import or pass 'ast' directly."
            )
        resolved_ast, _ = load_paper_ast(path)
    elif paper_path:
        resolved_ast, path_slug = load_paper_ast(paper_path)
        resolved_slug = slugify(slug or path_slug or resolved_ast.get("title") or "imported")
    else:
        raise ValueError(
            "Provide a paper source: 'ast' (paper AST dict), 'slug' "
            "(paper_dna_<slug> paper), or 'paper_path'."
        )

    return evaluate_ast_objective(
        resolved_ast,
        objective,
        slug=resolved_slug,
        embed=embed,
        top_k=top_k,
        collections=collections,
        per_collection_k=per_collection_k,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="[SPR-82.3] Target Objective / JD matching engine.")
    parser.add_argument("objective", help="target objective / JD requirement text")
    parser.add_argument("--slug", default=None, help="paper_dna_<slug> paper to evaluate (disk AST)")
    parser.add_argument("--ast", default=None, help="path to a canonical paper AST JSON file")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args()

    result = evaluate_objective(args.objective, slug=args.slug, paper_path=args.ast, top_k=args.top_k)
    print(json.dumps(result, indent=2))
