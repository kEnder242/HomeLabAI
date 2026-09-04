"""
[FEAT-540] Multi-Collection CLaRa-DNA Vector Pre-Triage Module
[FEAT-541] Two-Stage Zero-Duplicate RAG Cache Integration

Performs a sub-20ms FastEmbed CPU-only vector probe against ChromaDB port 8001
across behavioral_dna, feature_dna, long_term_wisdom, career_ledger, and blackboard_ledger_dna.

Generates pre-triage semantic anchors and topic hints to prime the 3B triage model
WITHOUT hardcoded keyword/regex overrides (BKM-015 compliance).
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global singletons for FastEmbed & ChromaDB
_fastembed_model = None
_chroma_client = None

PRE_TRIAGE_COLLECTIONS = [
    "behavioral_dna",
    "feature_dna",
    "long_term_wisdom",
    "career_ledger",
    "short_term_stream",
    "lab_journal"
]


def _get_embedding_model():
    global _fastembed_model
    if _fastembed_model is None:
        try:
            from fastembed import TextEmbedding
            _fastembed_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"[VECTOR_PRE_TRIAGE] FastEmbed initialization error: {e}")
            return None
    return _fastembed_model


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            _chroma_client = chromadb.HttpClient(host="127.0.0.1", port=8001)
            _chroma_client.heartbeat()
        except Exception as e:
            logger.warning(f"[VECTOR_PRE_TRIAGE] ChromaDB connection error: {e}")
            return None
    return _chroma_client


def probe_clara_dna_sync(query: str, top_k: int = 1) -> Dict[str, Any]:
    """
    Synchronous vector probe against CLaRa-DNA collections.
    Returns:
    {
        "min_distance": float,
        "best_collection": str,
        "best_meta": dict,
        "best_doc": str,
        "results_by_collection": dict,
        "semantic_hint": str,
        "is_casual_candidate": bool
    }
    """
    model = _get_embedding_model()
    client = _get_chroma_client()
    
    if not model or not client or not query or not query.strip():
        return {
            "min_distance": 1.0,
            "best_collection": "",
            "best_meta": {},
            "best_doc": "",
            "results_by_collection": {},
            "semantic_hint": "",
            "is_casual_candidate": False
        }
    
    try:
        query_vec = list(model.embed([query.strip()]))[0].tolist()
    except Exception as e:
        logger.error(f"[VECTOR_PRE_TRIAGE] Embedding generation error: {e}")
        return {
            "min_distance": 1.0,
            "best_collection": "",
            "best_meta": {},
            "best_doc": "",
            "results_by_collection": {},
            "semantic_hint": "",
            "is_casual_candidate": False
        }
    
    best_dist = 999.0
    best_col = ""
    best_meta = {}
    best_doc = ""
    results_by_col = {}
    
    for cname in PRE_TRIAGE_COLLECTIONS:
        try:
            col = client.get_collection(cname)
            res = col.query(
                query_embeddings=[query_vec],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            if res and res.get("distances") and res["distances"][0]:
                dist = res["distances"][0][0]
                meta = res["metadatas"][0][0] if res.get("metadatas") and res["metadatas"][0] else {}
                doc = res["documents"][0][0] if res.get("documents") and res["documents"][0] else ""
                results_by_col[cname] = {
                    "distance": dist,
                    "metadata": meta,
                    "document": doc
                }
                if dist < best_dist:
                    best_dist = dist
                    best_col = cname
                    best_meta = meta
                    best_doc = doc
        except Exception:
            continue
            
    # Formulate semantic pre-triage hint for LLM
    hint = ""
    if best_dist < 0.55:
        topic = best_meta.get("name") or best_meta.get("bkm_id") or best_meta.get("feature_id") or best_meta.get("domain") or best_col
        adapter = best_meta.get("adapter", "")
        hint = f"[VECTOR_MATCH]: Top match in '{best_col}' (topic: '{topic}', distance: {best_dist:.3f})."
        if best_col == "behavioral_dna":
            hint += " Contains BKM Protocol / Operational Guidance."
        elif best_col in ("short_term_stream", "lab_journal"):
            hint += " Matches recent conversation history / prior turns."
        elif adapter:
            hint += f" Suggested adapter/domain: {adapter}."
    elif best_dist > 0.68:
        hint = f"[VECTOR_MATCH]: Low archive semantic similarity (min_dist={best_dist:.3f} > 0.68)."

    is_casual = best_dist > 0.68

    return {
        "min_distance": best_dist if best_dist < 900 else 1.0,
        "best_collection": best_col,
        "best_meta": best_meta,
        "best_doc": best_doc,
        "results_by_collection": results_by_col,
        "semantic_hint": hint,
        "is_casual_candidate": is_casual
    }
