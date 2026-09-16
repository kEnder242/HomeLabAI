"""
[SPR-82.2] Paper-Scoped ChromaDB DNA Collections — comprehensive unit suite.
================================================================================
Verifies:
  • node-level chunking of the canonical two-tier AST (doc / section / bullet /
    paragraph) into ChromaDB records carrying the 7-key metadata envelope
    (node_id, node_type, heading, slug, bone_collection, citations,
    candidate_pool);
  • slug sanitization and ``paper_dna_<slug>`` collection naming;
  • sync_paper_dna() idempotent reindex (dict input, path input, dry-run,
    invalid input rejection);
  • list_paper_dna_collections() filtering and delete_paper_dna_collection()
    lifecycle teardown;
  • query_hybrid_dna() cross-collection merge + ranking (global DNA collections
    and the local paper_dna_<slug>);
  • POST /paper/query_scoped_dna handler behavior and the /paper/import DNA
    sync integration.

Hermetic: ChromaDB is never contacted — every test patches
``curator.sync_paper_dna.get_chroma_client`` with an in-memory fake (or patches
the query/sync functions directly); the handler tests use a mocked aiohttp
request and patched disk writes. Requires no live daemon and no ChromaDB server.
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

from curator.sync_paper_dna import (  # noqa: E402
    COLLECTION_PREFIX,
    GLOBAL_COLLECTIONS,
    build_chunks,
    collection_name,
    delete_paper_dna_collection,
    iter_paper_nodes,
    list_paper_dna_collections,
    query_dna_collection,
    query_hybrid_dna,
    slugify,
    sync_paper_dna,
)
from src.v5.foyer.router import FoyerRouter  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory ChromaDB fakes (mirror the HttpClient surface we rely on)
# ---------------------------------------------------------------------------
class FakeCollection:
    """Deterministic in-memory Chroma collection (add / delete / query)."""

    def __init__(self, name):
        self.name = name
        self.records = {}  # id -> (document, metadata)

    def add(self, ids, documents, metadatas):
        for i, cid in enumerate(ids):
            self.records[cid] = (documents[i], metadatas[i])

    def upsert(self, ids, documents, metadatas):
        self.add(ids, documents, metadatas)

    def delete(self, where=None):
        if not where:
            self.records.clear()
            return
        key, value = next(iter(where.items()))
        for cid in list(self.records):
            if self.records[cid][1].get(key) == value:
                del self.records[cid]

    def count(self):
        return len(self.records)

    def query(self, query_texts, n_results):
        # Distances 0.0, 0.05, ... (most-similar first, lower is closer).
        items = sorted(self.records.items())[: max(1, n_results)]
        return {
            "ids": [[cid for cid, _ in items]],
            "documents": [[doc for _, (doc, _meta) in items]],
            "metadatas": [[meta for _, (_doc, meta) in items]],
            "distances": [[round(0.05 * i, 4) for i in range(len(items))]],
        }


class FakeChromaClient:
    """In-memory stand-in for the ChromaDB HttpClient surface."""

    def __init__(self, collections=None):
        self._collections = collections if collections is not None else {}

    def get_or_create_collection(self, name, embedding_function=None):
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]

    def get_collection(self, name):
        if name not in self._collections:
            raise ValueError(f"Collection {name} does not exist.")
        return self._collections[name]

    def list_collections(self):
        return list(self._collections.values())

    def delete_collection(self, name):
        if name not in self._collections:
            raise ValueError(f"Collection {name} does not exist.")
        del self._collections[name]


def _patch_chroma(fake):
    return patch("curator.sync_paper_dna.get_chroma_client", return_value=fake)


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------
def _ast(**overrides):
    """A canonical two-tier AST (valid per validate_paper_schema.py)."""
    ast = {
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
                        "bullet_type": "bullet",
                        "text": "Built the BKM-010 fallback mesh end-to-end.",
                        "citations": ["FEAT-452"],
                        "bone_collection": [],
                        "_candidate_pool": ["BKM-044"],
                    },
                    {
                        "id": "p-02",
                        "bullet_type": "paragraph",
                        "text": "Operated the vLLM and Ollama dual-engine stack.",
                        "citations": [],
                        "bone_collection": [],
                        "_candidate_pool": [],
                    },
                ],
            },
            {
                "id": "sec-02",
                "heading": "Deterministic LaTeX Compilation",
                "bone_collection": [],
                "_candidate_pool": ["FEAT-213"],
                "paragraphs": [
                    {
                        "id": "p-03",
                        "bullet_type": "bullet",
                        "text": "Compiled zero-dependency PDFs from cached bones.",
                        "citations": [],
                        "bone_collection": ["FEAT-181"],
                        "_candidate_pool": [],
                    },
                ],
            },
        ],
    }
    ast.update(overrides)
    return ast


SAMPLE_SLUG = "resume"
EXPECTED_CHUNK_COUNT = 6  # 1 doc + 2 sections + 3 paragraphs


def _resp_body(response):
    """Decode the JSON payload of an aiohttp web.Response."""
    return json.loads(response.text)


async def _call_query_handler(payload):
    """Invoke FoyerRouter.handle_paper_query_scoped_dna offline with a mocked request."""
    request = MagicMock()
    request.json = AsyncMock(return_value=payload)
    return await FoyerRouter.handle_paper_query_scoped_dna(object(), request)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Slug & collection naming
# ---------------------------------------------------------------------------
def test_slugify_sanitizes():
    assert slugify("My Resume!") == "my-resume"
    assert slugify("  JITC Intuition  ") == "jitc-intuition"
    assert slugify("already-good_slug") == "already-good_slug"
    assert slugify("") == "imported"
    assert slugify(None) == "imported"


def test_collection_name_prefix():
    assert collection_name("jitc-intuition") == "paper_dna_jitc-intuition"
    assert collection_name("My Resume!") == "paper_dna_my-resume"
    assert COLLECTION_PREFIX == "paper_dna_"


# ---------------------------------------------------------------------------
# Node chunking (section / paragraph / bullet) + 7-key metadata envelope
# ---------------------------------------------------------------------------
def test_iter_paper_nodes_envelope_and_types():
    nodes = list(iter_paper_nodes(_ast(), SAMPLE_SLUG))
    node_types = [n["node_type"] for n in nodes]
    assert node_types == ["doc", "section", "bullet", "paragraph", "section", "bullet"]
    assert len(nodes) == EXPECTED_CHUNK_COUNT
    for node in nodes:
        for key in ("node_id", "node_type", "heading", "slug", "bone_collection",
                    "citations", "candidate_pool"):
            assert key in node
        assert node["slug"] == SAMPLE_SLUG
        assert node["node_id"].startswith(f"{SAMPLE_SLUG}:")
    # doc node carries the title as its heading, root pools as envelope
    assert nodes[0]["node_type"] == "doc"
    assert nodes[0]["heading"] == "Staff Infrastructure & AI Platforms Resume"
    assert nodes[0]["bone_collection"] == ["FEAT-181"]
    assert nodes[0]["candidate_pool"] == ["BKM-010"]
    # section node reflects the section-level two-tier pools
    assert nodes[1]["node_type"] == "section"
    assert nodes[1]["node_id"] == "resume:sec-01"
    assert nodes[1]["bone_collection"] == ["WIS-108"]


def test_build_chunks_metadata_envelope():
    chunks = build_chunks(_ast(), SAMPLE_SLUG)
    assert len(chunks) == EXPECTED_CHUNK_COUNT
    for chunk in chunks:
        meta = chunk["metadata"]
        assert meta["slug"] == SAMPLE_SLUG
        for key in ("node_id", "node_type", "heading", "slug",
                    "bone_collection", "citations", "candidate_pool"):
            assert key in meta
    bullet = chunks[2]
    assert bullet["metadata"]["node_type"] == "bullet"
    assert bullet["metadata"]["node_id"] == "resume:sec-01:p-01"
    assert bullet["metadata"]["heading"] == "Distributed AI Infrastructure"
    assert bullet["metadata"]["citations"] == ["FEAT-452"]
    assert bullet["metadata"]["candidate_pool"] == ["BKM-044"]
    assert bullet["metadata"]["bone_collection"] == []
    # paragraph text embeds the parent heading for retrieval context
    assert bullet["document"] == "Distributed AI Infrastructure: Built the BKM-010 fallback mesh end-to-end."


def test_build_chunks_deterministic_ids():
    first = build_chunks(_ast(), SAMPLE_SLUG)
    second = build_chunks(_ast(), SAMPLE_SLUG)
    assert [c["id"] for c in first] == [c["id"] for c in second]
    assert all(cid.startswith(f"paper_{SAMPLE_SLUG}_") for cid in [c["id"] for c in first])


# ---------------------------------------------------------------------------
# sync_paper_dna()
# ---------------------------------------------------------------------------
def test_sync_paper_dna_dict_input_uploads_all_nodes():
    fake = FakeChromaClient()
    with _patch_chroma(fake):
        stats = sync_paper_dna(_ast(), slug=SAMPLE_SLUG)
    assert stats["uploaded"] == EXPECTED_CHUNK_COUNT
    assert stats["slug"] == SAMPLE_SLUG
    assert stats["collection"] == "paper_dna_resume"
    assert stats["dry_run"] is False
    assert stats["node_types"] == {"doc": 1, "section": 2, "bullet": 2, "paragraph": 1}

    coll = fake.get_collection("paper_dna_resume")
    assert coll.count() == EXPECTED_CHUNK_COUNT
    metas = [meta for _, (_doc, meta) in coll.records.items()]
    slugs = {m["slug"] for m in metas}
    assert slugs == {SAMPLE_SLUG}
    types = {m["node_type"] for m in metas}
    assert types == {"doc", "section", "bullet", "paragraph"}


def test_sync_paper_dna_reindex_removes_stale_entries():
    fake = FakeChromaClient()
    with _patch_chroma(fake):
        sync_paper_dna(_ast(), slug=SAMPLE_SLUG)
        # Mutate the collection directly with a stale entry sharing the slug,
        # then resync — the stale record must be purged by the reindex delete.
        coll = fake.get_collection("paper_dna_resume")
        coll.add(ids=["stale-doc"], documents=["gone"], metadatas=[{"slug": SAMPLE_SLUG, "node_id": "stale"}])
        assert coll.count() == EXPECTED_CHUNK_COUNT + 1
        stats = sync_paper_dna(_ast(), slug=SAMPLE_SLUG)
    assert stats["uploaded"] == EXPECTED_CHUNK_COUNT
    assert fake.get_collection("paper_dna_resume").count() == EXPECTED_CHUNK_COUNT
    assert "stale-doc" not in fake.get_collection("paper_dna_resume").records


def test_sync_paper_dna_from_path(tmp_path):
    paper_file = tmp_path / "paper_jitc_intuition.json"
    paper_file.write_text(json.dumps(_ast()), encoding="utf-8")
    fake = FakeChromaClient()
    with _patch_chroma(fake):
        stats = sync_paper_dna(str(paper_file))
    # leading "paper_" prefix is stripped from the file stem
    assert stats["slug"] == "jitc-intuition"
    assert stats["collection"] == "paper_dna_jitc-intuition"
    assert fake.get_collection("paper_dna_jitc-intuition").count() == EXPECTED_CHUNK_COUNT


def test_sync_paper_dna_slug_priority():
    # explicit slug wins over AST title
    fake = FakeChromaClient()
    with _patch_chroma(fake):
        stats = sync_paper_dna(_ast(), slug="explicit")  # AST title contains "Resume"
    assert stats["slug"] == "explicit"
    # without an explicit slug the AST title is slugified
    fake2 = FakeChromaClient()
    with _patch_chroma(fake2):
        stats2 = sync_paper_dna(_ast())
    assert stats2["slug"] == "staff-infrastructure-ai-platforms-resume"


def test_sync_paper_dna_dry_run_never_touches_chroma():
    fake_client = MagicMock()
    with _patch_chroma(fake_client):
        stats = sync_paper_dna(_ast(), slug=SAMPLE_SLUG, dry_run=True)
    assert stats["uploaded"] == 0
    assert stats["chunks"] == EXPECTED_CHUNK_COUNT
    assert stats["dry_run"] is True
    assert stats["collection"] == "paper_dna_resume"
    fake_client.assert_not_called()
    # empty-section AST short-circuits without a client as well
    empty = {"title": "Empty", "sections": []}
    with _patch_chroma(fake_client):
        stats2 = sync_paper_dna(empty, slug="empty")
    assert stats2["uploaded"] == 1  # doc root node only
    fake_client.assert_not_called()


def test_sync_paper_dna_invalid_inputs():
    with pytest.raises(TypeError):
        sync_paper_dna(["not", "a", "dict"])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sync_paper_dna({"title": "missing sections key"})


# ---------------------------------------------------------------------------
# Collection lifecycle: list / delete
# ---------------------------------------------------------------------------
def test_list_paper_dna_collections_filters_paper_only():
    fake = FakeChromaClient({
        "paper_dna_beta": _seeded("paper_dna_beta", 1),
        "paper_dna_alpha": _seeded("paper_dna_alpha", 2),
        "feature_dna": _seeded("feature_dna", 99),
        "behavioral_dna": _seeded("behavioral_dna", 99),
    })
    with _patch_chroma(fake):
        result = list_paper_dna_collections()
    assert result == [
        {"slug": "alpha", "collection": "paper_dna_alpha", "count": 2},
        {"slug": "beta", "collection": "paper_dna_beta", "count": 1},
    ]


def test_list_paper_dna_collections_offline_returns_empty():
    with _patch_chroma(MagicMock(side_effect=RuntimeError("server down"))):
        assert list_paper_dna_collections() == []


def test_delete_paper_dna_collection():
    fake = FakeChromaClient({"paper_dna_resume": _seeded("paper_dna_resume", 3)})
    with _patch_chroma(fake):
        result = delete_paper_dna_collection("resume")
        assert result == {"status": "deleted", "collection": "paper_dna_resume", "slug": "resume"}
        assert "paper_dna_resume" not in fake._collections
        # second delete of the same slug -> not_found (idempotent teardown)
        result2 = delete_paper_dna_collection("resume")
    assert result2["status"] == "not_found"
    assert result2["collection"] == "paper_dna_resume"


def _seeded(name, count):
    coll = FakeCollection(name)
    coll.add(
        ids=[f"{name}-{i}" for i in range(count)],
        documents=[f"Seeded document {i} for {name}" for i in range(count)],
        metadatas=[{"slug": name, "node_id": f"{name}:{i}"} for i in range(count)],
    )
    return coll


# ---------------------------------------------------------------------------
# Hybrid cross-collection queries (Phase 1 DISCOVER semantics)
# ---------------------------------------------------------------------------
def test_query_hybrid_dna_merges_paper_and_global_collections():
    fake = FakeChromaClient({
        "paper_dna_resume": _seeded("paper_dna_resume", 3),
        "feature_dna": _seeded("feature_dna", 3),
        "behavioral_dna": _seeded("behavioral_dna", 3),
        "long_term_wisdom": _seeded("long_term_wisdom", 3),
    })
    with _patch_chroma(fake):
        results = query_hybrid_dna("vllm fallback mesh", slug="resume", top_k=10)
    # paper-scoped collection ranks first (3 hits), all globals represented
    assert len(results) == 10
    assert results[0]["collection"] == "paper_dna_resume"
    covered = {r["collection"] for r in results}
    assert covered == {"paper_dna_resume", "feature_dna", "behavioral_dna", "long_term_wisdom"}
    # ranked by similarity score (1 - distance), non-increasing
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["score"] == 1.0  # distance 0.0 for the fake's first hit


def test_query_hybrid_dna_without_slug_skips_paper():
    fake = FakeChromaClient({
        "feature_dna": _seeded("feature_dna", 2),
        "behavioral_dna": _seeded("behavioral_dna", 2),
        "long_term_wisdom": _seeded("long_term_wisdom", 2),
    })
    with _patch_chroma(fake):
        results = query_hybrid_dna("anything", slug=None, top_k=10)
    covered = {r["collection"] for r in results}
    assert "paper_dna_" not in " ".join(covered)
    assert covered == {"feature_dna", "behavioral_dna", "long_term_wisdom"}
    assert len(results) == 6


def test_query_hybrid_dna_dedupes_per_collection():
    # identical hit ids across collections are kept (distinct (collection, id)); a
    # duplicate within one collection is impossible from Chroma so this guards the
    # (collection, id) de-dup key shape only.
    fake = FakeChromaClient({
        "feature_dna": _seeded("feature_dna", 2),
        "behavioral_dna": _seeded("feature_dna", 2),  # same ids, different collection
    })
    with _patch_chroma(fake):
        results = query_hybrid_dna("x", slug=None, top_k=10)
    assert len(results) == 4  # 2 per collection, no cross-collection collapse


def test_query_dna_collection_missing_collection_returns_empty():
    fake = FakeChromaClient({})
    with _patch_chroma(fake):
        hits = query_dna_collection(fake, "paper_dna_missing", "query", top_k=5)
    assert hits == []


# ---------------------------------------------------------------------------
# POST /paper/query_scoped_dna handler
# ---------------------------------------------------------------------------
def test_route_registered():
    def path_of(route):
        resource = getattr(route, "resource", None)
        return getattr(resource, "canonical", None) if resource else None

    routes = FoyerRouter(disable_ear=True).app.router.routes()
    paths = {(route.method, path_of(route)) for route in routes}
    assert ("POST", "/paper/query_scoped_dna") in paths
    assert ("POST", "/attendant/paper/query_scoped_dna") in paths


@pytest.mark.asyncio
async def test_handle_paper_query_scoped_dna_success():
    fake_results = [
        {"id": "paper_resume_abc", "collection": "paper_dna_resume", "node_id": "resume:sec-01",
         "node_type": "section", "heading": "Distributed AI Infrastructure", "slug": "resume",
         "document": "Distributed AI Infrastructure", "distance": 0.1, "score": 0.9},
        {"id": "FEAT-181", "collection": "feature_dna", "node_id": "FEAT-181", "node_type": "",
         "heading": "", "slug": "", "document": "FEAT-181", "distance": 0.2, "score": 0.8},
    ]
    with patch("curator.sync_paper_dna.query_hybrid_dna", return_value=fake_results) as mock_query:
        response = await _call_query_handler({"query": "vllm fallback mesh", "slug": "resume", "top_k": 7})
    assert response.status == 200
    body = _resp_body(response)
    assert body["status"] == "success"
    assert body["query"] == "vllm fallback mesh"
    assert body["slug"] == "resume"
    assert body["count"] == 2
    assert body["results"][0]["collection"] == "paper_dna_resume"
    mock_query.assert_called_once_with(
        "vllm fallback mesh", slug="resume", collections=None, top_k=7
    )


@pytest.mark.asyncio
async def test_handle_paper_query_scoped_dna_accepts_text_alias():
    with patch("curator.sync_paper_dna.query_hybrid_dna", return_value=[]) as mock_query:
        response = await _call_query_handler({"text": "mesh", "slug": "resume"})
    assert response.status == 200
    mock_query.assert_called_once_with("mesh", slug="resume", collections=None, top_k=10)


@pytest.mark.asyncio
async def test_handle_paper_query_scoped_dna_missing_query_400():
    response = await _call_query_handler({"slug": "resume"})
    assert response.status == 400
    assert "Missing query text" in _resp_body(response)["message"]


# ---------------------------------------------------------------------------
# POST /paper/import DNA sync integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handle_paper_import_integrates_dna_sync():
    request = MagicMock()
    request.json = AsyncMock(return_value={
        "title": "Ops Resume",
        "content": "# Ops Resume\n\n## Platform\n\nRan BKM-010 tests and shipped FEAT-181.\n",
    })
    fake_sync = {"uploaded": 3, "slug": "ops-resume", "collection": "paper_dna_ops-resume"}
    with patch("src.v5.foyer.router.atomic_write_json") as mock_write, \
         patch("curator.sync_paper_dna.sync_paper_dna", return_value=fake_sync) as mock_sync:
        response = await FoyerRouter.handle_paper_import(object(), request)  # type: ignore[arg-type]
    assert response.status == 200
    body = _resp_body(response)
    assert body["status"] == "success"
    assert body["dna_sync"] == fake_sync
    assert body["stats"]["sections"] == 1
    mock_write.assert_called()
    mock_sync.assert_called_once()
    _args, kwargs = mock_sync.call_args
    assert kwargs.get("slug") == "ops-resume"
    assert _args[0]["title"] == "Ops Resume"


@pytest.mark.asyncio
async def test_handle_paper_import_dna_sync_failure_is_non_fatal():
    request = MagicMock()
    request.json = AsyncMock(return_value={
        "title": "Offline Paper",
        "content": "# Offline Paper\n\n## Body\n\nContent that cannot reach ChromaDB.\n",
    })
    with patch("src.v5.foyer.router.atomic_write_json"), \
         patch("curator.sync_paper_dna.sync_paper_dna", side_effect=RuntimeError("chroma down")):
        response = await FoyerRouter.handle_paper_import(object(), request)  # type: ignore[arg-type]
    assert response.status == 200
    body = _resp_body(response)
    assert body["status"] == "success"
    assert body["dna_sync"]["status"] == "error"
    assert "chroma down" in body["dna_sync"]["error"]
    assert body["file"].endswith(".json")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
