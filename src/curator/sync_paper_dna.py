#!/usr/bin/env python3
"""[SPR-82.2] Paper-Scoped ChromaDB DNA Collections — dynamic collection lifecycle.

Dedicated ChromaDB sync for paper-scoped DNA. Implements Story 82.2 of
SPR-82.0 (Generic Scoped Document Ingestion, Decoupled Two-Tier AST Palette):

* **Dynamic collection lifecycle** — every paper imports into its own
  ``paper_dna_<slug>`` collection on ChromaDB port 8001 (HttpClient with
  PersistentClient fallback), with ``list_paper_dna_collections()`` and
  ``delete_paper_dna_collection(slug)`` teardown support.
* **Node-level chunking** — each two-tier AST node (document root, section,
  paragraph/bullet) is chunked into a ChromaDB record carrying the 7-key
  metadata envelope: ``node_id``, ``node_type``, ``heading``, ``slug``,
  ``bone_collection``, ``citations``, ``candidate_pool``.
* **Idempotent reindex** — a resync deletes prior entries for the same slug
  before re-adding, so the collection always mirrors the current AST.
* **Hybrid cross-collection queries** — ``query_hybrid_dna()`` searches the
  global DNA collections (``feature_dna``, ``behavioral_dna``,
  ``long_term_wisdom``) and the local ``paper_dna_<slug>`` collection in a
  single ranked pass (Phase 1 DISCOVER semantics).

BKM-055 invariant: sync and query degrade gracefully (log + empty result)
when ChromaDB is unreachable — document ingestion/editing never stalls on an
offline database port.
"""

import hashlib
import json
import logging
import os
import re

import chromadb
from chromadb.utils import embedding_functions

# Config ---------------------------------------------------------------------
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))
COLLECTION_PREFIX = "paper_dna_"
GLOBAL_COLLECTIONS = ("feature_dna", "behavioral_dna", "long_term_wisdom")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

logger = logging.getLogger("paper_dna")


# ----------------------------------------------------------------------------
# Slug / naming helpers
# ----------------------------------------------------------------------------
def slugify(text):
    """Derive a safe paper slug from a title or filename (mirrors router safe_slug)."""
    if not text:
        return "imported"
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(text).lower().strip())
    slug = slug.strip("-")
    return slug or "imported"


def collection_name(slug):
    """Canonical paper-scoped collection name: ``paper_dna_<slug>``."""
    return f"{COLLECTION_PREFIX}{slugify(slug)}"


# ----------------------------------------------------------------------------
# Chroma plumbing (mirrors Portfolio_Dev/sync_chroma_dna.py conventions)
# ----------------------------------------------------------------------------
def get_chroma_client():
    """HttpClient on port 8001 with PersistentClient fallback."""
    try:
        logger.info("Attempting to connect to ChromaDB HttpClient on port %s:%s...", CHROMA_HOST, CHROMA_PORT)
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
        logger.info("HttpClient heartbeat successful.")
        return client
    except Exception as e:
        logger.warning("HttpClient connection failed: %s. Falling back to PersistentClient.", e)
        return chromadb.PersistentClient(path=DB_PATH)


def get_safe_collection(client, name, ef):
    try:
        return client.get_or_create_collection(name=name, embedding_function=ef)
    except Exception:
        return client.get_or_create_collection(name=name)


# ----------------------------------------------------------------------------
# Node chunking (two-tier AST -> flat ChromaDB records)
# ----------------------------------------------------------------------------
_STR = lambda items: [str(i) for i in (items or [])]  # noqa: E731  (coerce pool lists)


def iter_paper_nodes(ast, slug):
    """Yield every two-tier AST node as a flat chunk-field dict.

    Each yielded dict carries the 7 metadata keys the DISCOVER phase consumes:
    ``node_id``, ``node_type``, ``heading``, ``slug``, ``bone_collection``,
    ``citations``, ``candidate_pool``. Node types: ``doc`` (document root),
    ``section``, and the paragraph ``bullet_type`` (``bullet`` | ``paragraph``).
    """
    title = str(ast.get("title") or slug or "imported")
    yield {
        "node_id": f"{slug}:root",
        "node_type": "doc",
        "heading": title,
        "slug": slug,
        "text": title,
        "bone_collection": _STR(ast.get("bone_collection")),
        "citations": [],
        "candidate_pool": _STR(ast.get("_candidate_pool")),
    }
    for sec_idx, sec in enumerate(ast.get("sections") or [], start=1):
        sec_id = sec.get("id") or f"sec-{sec_idx:02d}"
        heading = str(sec.get("heading") or "").strip() or sec_id
        yield {
            "node_id": f"{slug}:{sec_id}",
            "node_type": "section",
            "heading": heading,
            "slug": slug,
            "text": heading,
            "bone_collection": _STR(sec.get("bone_collection")),
            "citations": [],
            "candidate_pool": _STR(sec.get("_candidate_pool")),
        }
        for par_idx, par in enumerate(sec.get("paragraphs") or [], start=1):
            text = str(par.get("text") or "").strip()
            if not text:
                continue
            par_id = par.get("id") or f"p-{par_idx:02d}"
            yield {
                "node_id": f"{slug}:{sec_id}:{par_id}",
                "node_type": par.get("bullet_type") or "paragraph",
                "heading": heading,
                "slug": slug,
                "text": text,
                "bone_collection": _STR(par.get("bone_collection")),
                "citations": _STR(par.get("citations")),
                "candidate_pool": _STR(par.get("_candidate_pool")),
            }


def _chunk_id(slug, node_id):
    digest = hashlib.md5(node_id.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"paper_{slug}_{digest}"


def build_chunks(ast, slug):
    """Convert a canonical two-tier paper AST into ChromaDB-ready chunk records.

    Returns a list of ``{id, document, metadata}`` dicts. Paragraph text is
    embedded with its section heading prefix for retrieval context; every
    metadata record carries the full 7-key paper DNA envelope. Deterministic
    ids (slug + md5 node_id) make resyncs idempotent.
    """
    chunks = []
    for node in iter_paper_nodes(ast, slug):
        if node["node_type"] in ("doc", "section"):
            document = node["text"]
        else:
            document = f"{node['heading']}: {node['text']}" if node["heading"] else node["text"]
        metadata = {
            "node_id": node["node_id"],
            "node_type": node["node_type"],
            "heading": node["heading"],
            "slug": slug,
            "bone_collection": node["bone_collection"],
            "citations": node["citations"],
            "candidate_pool": node["candidate_pool"],
        }
        chunks.append({
            "id": _chunk_id(slug, node["node_id"]),
            "document": document,
            "metadata": metadata,
        })
    return chunks


# ----------------------------------------------------------------------------
# Paper AST input normalization
# ----------------------------------------------------------------------------
def load_paper_ast(paper_path_or_dict):
    """Normalize input to ``(ast, path_slug)``.

    * ``dict`` -> used directly as the canonical AST (path_slug ``None``).
    * ``str``/``Path`` -> parsed as a paper JSON file; the slug is derived
      from the file stem (a leading ``paper_`` prefix is stripped).
    Raises ``TypeError`` for unsupported types and ``ValueError`` when the
    payload is not a canonical two-tier AST (missing ``sections`` list).
    """
    if isinstance(paper_path_or_dict, dict):
        ast = paper_path_or_dict
        path_slug = None
    elif isinstance(paper_path_or_dict, (str, os.PathLike)):
        path = os.fspath(paper_path_or_dict)
        with open(path, "r", encoding="utf-8") as fh:
            ast = json.load(fh)
        stem = os.path.splitext(os.path.basename(path))[0]
        stem = re.sub(r"^paper_", "", stem)
        path_slug = slugify(stem.replace("_", "-"))
    else:
        raise TypeError(
            "paper_path_or_dict must be a dict (canonical AST) or a path to a "
            "paper JSON file"
        )
    if not isinstance(ast, dict) or not isinstance(ast.get("sections"), list):
        raise ValueError(
            "paper AST must be a dict containing a 'sections' list "
            "(canonical two-tier schema)"
        )
    return ast, path_slug


# ----------------------------------------------------------------------------
# Collection lifecycle
# ----------------------------------------------------------------------------
def sync_paper_dna(paper_path_or_dict, slug=None, dry_run=False):
    """[SPR-82.2] Sync a paper's two-tier AST into its scoped ``paper_dna_<slug>`` collection.

    Chunks every node (doc root, section, paragraph/bullet) into ChromaDB
    records carrying the 7-key metadata envelope, re-indexes the collection
    idempotently (deletes prior entries for the same slug, then adds), and
    returns upload stats.

    Accepts a canonical AST dict or a path to a paper JSON file. ``slug``
    overrides slug derivation (explicit slug > AST title > file stem).
    ``dry_run=True`` parses and chunks without touching ChromaDB (returns
    chunk stats only — no client is constructed).
    """
    ast, path_slug = load_paper_ast(paper_path_or_dict)
    resolved_slug = slugify(slug or path_slug or ast.get("title") or "imported")
    chunks = build_chunks(ast, resolved_slug)

    if dry_run or not chunks:
        return {
            "uploaded": 0 if dry_run else len(chunks),
            "slug": resolved_slug,
            "chunks": len(chunks),
            "collection": collection_name(resolved_slug),
            "dry_run": dry_run,
        }

    client = get_chroma_client()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=DEFAULT_EMBEDDING_MODEL
    )
    collection = get_safe_collection(client, collection_name(resolved_slug), ef)

    try:
        collection.delete(where={"slug": resolved_slug})
    except Exception as e:
        logger.warning("paper_dna reindex delete note (%s): %s", resolved_slug, e)

    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["document"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    logger.info("[paper_dna] Synced %d chunks into %s", len(chunks), collection.name)
    return {
        "uploaded": len(chunks),
        "slug": resolved_slug,
        "chunks": len(chunks),
        "collection": collection_name(resolved_slug),
        "dry_run": False,
        "node_types": {
            node_type: sum(1 for c in chunks if c["metadata"]["node_type"] == node_type)
            for node_type in ("doc", "section", "bullet", "paragraph")
        },
    }


def list_paper_dna_collections():
    """Return ``[{slug, collection, count}]`` for every ``paper_dna_*`` collection.

    Non-paper collections on the server are ignored. Returns ``[]`` when
    ChromaDB is unreachable (graceful degradation per BKM-055).
    """
    try:
        client = get_chroma_client()
        out = []
        for coll in client.list_collections():
            name = getattr(coll, "name", None)
            if not name or not name.startswith(COLLECTION_PREFIX):
                continue
            count = 0
            try:
                count = coll.count()
            except Exception:
                count = 0
            out.append({
                "slug": name[len(COLLECTION_PREFIX):],
                "collection": name,
                "count": count,
            })
        return sorted(out, key=lambda x: x["slug"])
    except Exception as e:
        logger.warning("paper_dna list collections note: %s", e)
        return []


def delete_paper_dna_collection(slug):
    """Delete the paper-scoped collection for ``slug`` (lifecycle teardown).

    Returns ``{"status": "deleted", ...}`` on success, ``{"status": "not_found", ...}``
    when no such collection exists, and ``{"status": "error", ...}`` for
    transport-level failures (ChromaDB unreachable, etc.).
    """
    name = collection_name(slug)
    try:
        client = get_chroma_client()
        client.delete_collection(name)
        logger.info("[paper_dna] Deleted collection %s", name)
        return {"status": "deleted", "collection": name, "slug": slugify(slug)}
    except Exception as e:
        msg = str(e)
        if "not exist" in msg.lower() or "doesn't exist" in msg.lower():
            return {"status": "not_found", "collection": name, "slug": slugify(slug)}
        logger.warning("paper_dna delete collection note (%s): %s", name, e)
        return {"status": "error", "collection": name, "slug": slugify(slug), "error": msg}


# ----------------------------------------------------------------------------
# Hybrid cross-collection queries (Phase 1 DISCOVER semantics)
# ----------------------------------------------------------------------------
def query_dna_collection(client, name, query_text, top_k=5):
    """Run a single ChromaDB query against one DNA collection; returns ranked hits."""
    try:
        collection = client.get_collection(name=name)
    except Exception as e:
        logger.warning("paper_dna query: collection %s unavailable (%s)", name, e)
        return []
    try:
        res = collection.query(query_texts=[query_text], n_results=max(1, top_k))
    except Exception as e:
        logger.warning("paper_dna query failed on %s: %s", name, e)
        return []
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    hits = []
    for i, cid in enumerate(ids):
        meta = metas[i] if i < len(metas) and metas[i] else {}
        dist = dists[i] if i < len(dists) else None
        hits.append({
            "id": cid,
            "collection": name,
            "node_id": meta.get("node_id") or cid,
            "node_type": meta.get("node_type") or "",
            "heading": meta.get("heading") or "",
            "slug": meta.get("slug") or "",
            "document": docs[i] if i < len(docs) else "",
            "distance": dist,
            "score": round(1.0 - dist, 4) if isinstance(dist, (int, float)) else None,
        })
    return hits


def query_hybrid_dna(query_text, slug=None, collections=GLOBAL_COLLECTIONS, top_k=10, per_collection_k=5):
    """[SPR-82.2] Hybrid cross-collection DNA search.

    Executes the same query against each global DNA collection (default
    ``feature_dna``, ``behavioral_dna``, ``long_term_wisdom``) and, when a
    paper ``slug`` is given, against the local ``paper_dna_<slug>`` collection
    first. Hits are merged, de-duplicated by ``(collection, id)``, ranked by
    similarity score (``1 - distance``), and truncated to ``top_k``. Unreachable
    or missing collections are skipped (never fatal).
    """
    client = get_chroma_client()
    targets = [collection_name(slug)] if slug else []
    targets += list(collections)
    merged, seen = [], set()
    for name in targets:
        for hit in query_dna_collection(client, name, query_text, top_k=per_collection_k):
            key = (hit["collection"], hit["id"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    merged.sort(
        key=lambda h: (h["score"] is not None, h["score"] if h["score"] is not None else -1),
        reverse=True,
    )
    return merged[:top_k]


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="[SPR-82.2] paper_dna_<slug> ChromaDB sync & lifecycle.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="sync a paper JSON file/dict into paper_dna_<slug>")
    p_sync.add_argument("paper", help="path to a canonical paper AST JSON file")
    p_sync.add_argument("--slug", default=None, help="override the derived collection slug")
    p_sync.add_argument("--dry-run", action="store_true", help="parse/chunk only, no ChromaDB write")

    sub.add_parser("list", help="list all paper_dna_* collections")

    p_delete = sub.add_parser("delete", help="delete a paper_dna_<slug> collection")
    p_delete.add_argument("slug")

    args = parser.parse_args()
    if args.command == "sync":
        print(json.dumps(sync_paper_dna(args.paper, slug=args.slug, dry_run=args.dry_run), indent=2))
    elif args.command == "list":
        print(json.dumps(list_paper_dna_collections(), indent=2))
    elif args.command == "delete":
        print(json.dumps(delete_paper_dna_collection(args.slug), indent=2))
