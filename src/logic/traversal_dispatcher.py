"""
[FEAT-117/467] Bidirectional Traversal Dispatcher

Pure, decoupled module implementing traversal mode routing for the RAG
retrieval pipeline. Supports bidirectional query synthesis:

  - TOPIC_FIRST: Keyword / Silicon Spec → Epochs / Gems / BKMs
  - TIME_FIRST: Time / Era / Year Anchor → Keywords / Narratives
  - STREAM_REPLAY: Short-term stream (zero career notes)

BKM-015 Compliant: zero third-party dependencies beyond the Python standard library.
Class 1 Design: no test-framework imports in production code.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


# ─── Traversal Mode Enum ────────────────────────────────────────────────────

class TraversalMode(str, Enum):
    """Supported traversal modes for bidirectional RAG routing."""
    TOPIC_FIRST = "TOPIC_FIRST"
    TIME_FIRST = "TIME_FIRST"
    STREAM_REPLAY = "STREAM_REPLAY"


# ─── Collection Scope Constants ─────────────────────────────────────────────

# Primary collections for each traversal mode
_MODE_COLLECTIONS: dict[TraversalMode, list[str]] = {
    TraversalMode.TOPIC_FIRST: ["artifact_vault", "behavioral_dna"],
    TraversalMode.TIME_FIRST: ["career_ledger", "artifact_vault"],
    TraversalMode.STREAM_REPLAY: ["short_term_stream"],
}

# Keyword families for TOPIC_FIRST synthesis
_TOPIC_KEYWORD_FAMILIES: dict[str, list[str]] = {
    "silicon": ["silicon", "validation", "silicon_spec", "silicon_telemetry", "exp_tlm"],
    "protocol": ["protocol", "bkm", "best_known_method", "sre", "playbook"],
    "code": ["code", "implementation", "module", "node", "engine", "adapter"],
    "architecture": ["architecture", "system", "design", "topology", "wiring"],
    "forensic": ["forensic", "log", "telemetry", "diagnostic", "telemetry_collector"],
    "career": ["career", "experience", "role", "position", "responsibility"],
}

# Temporal anchor patterns
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_SPRINT_PATTERN = re.compile(r"(?i)\bsprint\s+(\d+)\b")
_ERA_PATTERN = re.compile(r"(?i)\b(early|mid|late|recent|current)\s*(career|phase|era|period)\b")


# ─── Temporal Extraction ────────────────────────────────────────────────────

def extract_temporal_anchors(query: str) -> dict[str, Any]:
    """
    Extract temporal year anchors, sprint references, and era markers from query.

    Args:
        query: The raw user query string.

    Returns:
        Dict with keys:
          - years: list of int years found (e.g. [2018, 2024])
          - sprints: list of int sprint numbers (e.g. [35, 62])
          - eras: list of str era markers (e.g. ["early career"])
          - has_temporal: bool indicating any temporal anchor found
    """
    years = [int(y) for y in _YEAR_PATTERN.findall(query)]
    # findall returns tuples, reconstruct full years
    year_matches = re.findall(r"\b((?:19|20)\d{2})\b", query)
    years = [int(y) for y in year_matches]

    sprint_matches = _SPRINT_PATTERN.findall(query)
    sprints = [int(s) for s in sprint_matches]

    era_matches = _ERA_PATTERN.findall(query)
    eras = [f"{e[0]} {e[1]}" for e in era_matches] if era_matches else []

    return {
        "years": years,
        "sprints": sprints,
        "eras": eras,
        "has_temporal": bool(years or sprints or eras),
    }



# ─── Query Formatting ───────────────────────────────────────────────────────

def _prioritize_topic_keywords(query: str) -> list[str]:
    """
    Identify and prioritize topic keywords from query by family.

    Returns a list of (family, keyword) tuples sorted by relevance.
    """
    query_lower = query.lower()
    prioritized = []

    for family, keywords in _TOPIC_KEYWORD_FAMILIES.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                prioritized.append((family, kw))

    # Silicon and protocol get highest priority
    priority_order = {"silicon": 0, "protocol": 1, "code": 2, "forensic": 3,
                      "architecture": 4, "career": 5}
    prioritized.sort(key=lambda x: priority_order.get(x[0], 99))

    return [kw for _, kw in prioritized]


def _build_topic_first_query(query: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Build a TOPIC_FIRST traversal query focusing on protocol/silicon/code keywords.

    Synthesizes a topic-centric query that prioritizes artifact_vault and
    behavioral_dna collections, enriching with keyword families.
    """
    keywords = _prioritize_topic_keywords(query)
    meta = metadata or {}

    # Build enriched query with keyword families
    enriched_terms = list(keywords) if keywords else [query]

    # Add metadata hints (e.g. domain from triage)
    if "domain" in meta:
        enriched_terms.insert(0, meta["domain"])

    return {
        "query_text": query,
        "enriched_terms": enriched_terms,
        "mode": TraversalMode.TOPIC_FIRST.value,
        "collections": _MODE_COLLECTIONS[TraversalMode.TOPIC_FIRST],
        "temporal_bounds": None,
        "boost_artifact_vault": True,
        "boost_behavioral_dna": True,
    }


def _build_time_first_query(query: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Build a TIME_FIRST traversal query extracting temporal year anchors.

    Parses temporal references and sets bounds for career_ledger/artifact_vault.
    """
    temporal = extract_temporal_anchors(query)
    meta = metadata or {}

    # Determine temporal bounds
    years = temporal["years"]
    sprints = temporal["sprints"]
    eras = temporal["eras"]

    temporal_bounds = None
    if years:
        temporal_bounds = {
            "type": "year_range",
            "start_year": min(years),
            "end_year": max(years),
        }
    elif sprints:
        temporal_bounds = {
            "type": "sprint_range",
            "sprints": sprints,
        }
    elif eras:
        temporal_bounds = {
            "type": "era",
            "eras": eras,
        }

    # Allow metadata override
    if "temporal_bounds" in meta:
        temporal_bounds = meta["temporal_bounds"]

    return {
        "query_text": query,
        "enriched_terms": temporal["years"] + [f"sprint {s}" for s in sprints] + eras,
        "mode": TraversalMode.TIME_FIRST.value,
        "collections": _MODE_COLLECTIONS[TraversalMode.TIME_FIRST],
        "temporal_bounds": temporal_bounds,
        "boost_career_ledger": True,
        "boost_artifact_vault": True,
    }


def _build_stream_replay_query(query: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Build a STREAM_REPLAY traversal query targeting recent session/dream history.

    Zero career notes - only short-term stream.
    """
    meta = metadata or {}
    session_limit = meta.get("session_limit", 10)

    return {
        "query_text": query,
        "enriched_terms": [query],
        "mode": TraversalMode.STREAM_REPLAY.value,
        "collections": ["short_term_stream"],
        "temporal_bounds": None,
        "session_limit": session_limit,
        "exclude_career_notes": True,
    }



# ─── Mode Dispatch Table ────────────────────────────────────────────────────

_MODE_BUILDERS: dict[TraversalMode, Any] = {
    TraversalMode.TOPIC_FIRST: _build_topic_first_query,
    TraversalMode.TIME_FIRST: _build_time_first_query,
    TraversalMode.STREAM_REPLAY: _build_stream_replay_query,
}


# ─── Public API ─────────────────────────────────────────────────────────────

def format_traversal_query(
    query: str,
    traversal_mode: str | TraversalMode,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Format a traversal query based on the specified mode.

    This is the primary entry point for query synthesis. It dispatches to the
    appropriate mode-specific builder to produce a structured query dict
    suitable for the RAG retrieval pipeline.

    Args:
        query: The raw user query string.
        traversal_mode: One of the TraversalMode values (str or enum).
        metadata: Optional dict with mode-specific overrides (e.g. temporal_bounds,
                  domain, feature_ids, session_limit).

    Returns:
        Dict containing:
          - query_text: Original query
          - enriched_terms: List of synthesized/extracted terms
          - mode: The traversal mode string
          - collections: List of target collection names
          - temporal_bounds: Optional temporal bounds dict
          - Additional mode-specific fields

    Raises:
        ValueError: If traversal_mode is not a valid TraversalMode value.
    """
    if not query or not query.strip():
        return {
            "query_text": query or "",
            "enriched_terms": [],
            "mode": traversal_mode.value if isinstance(traversal_mode, TraversalMode) else str(traversal_mode),
            "collections": [],
            "temporal_bounds": None,
        }

    # Normalize to enum
    if isinstance(traversal_mode, str):
        try:
            mode = TraversalMode(traversal_mode)
        except ValueError:
            raise ValueError(
                f"Invalid traversal mode: {traversal_mode!r}. "
                f"Valid modes: {[m.value for m in TraversalMode]}"
            )
    else:
        mode = traversal_mode

    builder = _MODE_BUILDERS[mode]
    return builder(query.strip(), metadata)


def resolve_collection_scope(
    vibe: str,
    domain: str | None = None,
    traversal_mode: str | TraversalMode = TraversalMode.TOPIC_FIRST,
) -> list[str]:
    """
    Resolve the target collection scope based on vibe, domain, and traversal mode.

    Determines which ChromaDB collections should be queried based on the
    combination of vibe classification, domain, and traversal mode.

    Args:
        vibe: The classified vibe (e.g. "TECHNICAL", "HISTORICAL", "CASUAL").
        domain: Optional domain hint (e.g. "exp_tlm", "exp_bkm", "lab_history").
        traversal_mode: The traversal mode to resolve collections for.

    Returns:
        List of collection name strings to query.
    """
    # Normalize traversal mode
    if isinstance(traversal_mode, str):
        try:
            mode = TraversalMode(traversal_mode)
        except ValueError:
            mode = TraversalMode.TOPIC_FIRST
    else:
        mode = traversal_mode

    # Base collections from mode
    base_collections = list(_MODE_COLLECTIONS.get(mode, ["artifact_vault"]))

    # Vibe-based overrides
    vibe_lower = vibe.upper() if vibe else ""

    # CASUAL/SUPERVISORY vibes skip heavy collections
    if vibe_lower in ("CASUAL", "SUPERVISORY", "META"):
        return ["short_term_stream"]

    # STREAM_REPLAY always targets short-term only
    if mode == TraversalMode.STREAM_REPLAY:
        return ["short_term_stream"]

    # HISTORICAL vibe boosts career_ledger
    if vibe_lower == "HISTORICAL":
        if "career_ledger" not in base_collections:
            base_collections.append("career_ledger")

    # TECHNICAL vibe boosts behavioral_dna
    if vibe_lower == "TECHNICAL":
        if "behavioral_dna" not in base_collections:
            base_collections.append("behavioral_dna")

    # Domain-based collection routing
    if domain:
        domain_lower = domain.lower()
        if domain_lower in ("exp_tlm", "silicon"):
            if "artifact_vault" not in base_collections:
                base_collections.append("artifact_vault")
        elif domain_lower in ("exp_bkm", "sre"):
            if "behavioral_dna" not in base_collections:
                base_collections.append("behavioral_dna")
        elif domain_lower in ("lab_history", "career"):
            if "career_ledger" not in base_collections:
                base_collections.append("career_ledger")

    # Preserve order, deduplicate
    seen: set[str] = set()
    result: list[str] = []
    for coll in base_collections:
        if coll not in seen:
            seen.add(coll)
            result.append(coll)

    return result


# ─── Convenience Aliases ────────────────────────────────────────────────────

def get_temporal_bounds(query: str) -> dict[str, Any] | None:
    """
    Quick extraction of temporal bounds from a query string.

    Returns None if no temporal anchors found.
    """
    temporal = extract_temporal_anchors(query)
    if not temporal["has_temporal"]:
        return None

    if temporal["years"]:
        return {
            "type": "year_range",
            "start_year": min(temporal["years"]),
            "end_year": max(temporal["years"]),
        }
    elif temporal["sprints"]:
        return {
            "type": "sprint_range",
            "sprints": temporal["sprints"],
        }
    elif temporal["eras"]:
        return {
            "type": "era",
            "eras": temporal["eras"],
        }
    return None


def is_temporal_query(query: str) -> bool:
    """Check if a query contains temporal anchors (years, sprints, eras)."""
    return extract_temporal_anchors(query)["has_temporal"]
