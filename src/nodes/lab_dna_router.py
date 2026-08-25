"""
[FEAT-469] Lab DNA Router Satellite

Pure, decoupled routing logic for DNA collection priority selection and
candidate context filtering. Implements the "Zero Context > Default Context"
principle: when retrieval quality is uncertain, the system provides zero
context rather than injecting misleading default data.

Collections:
    feature_dna        – FEAT/FEAT-series feature tracking
    lab_infrastructure – LAB-series infrastructure status
    lab_journal        – Lab session journal entries
    career_ledger      – Historical career notes (suppressed for live ops)
    behavioral_dna     – AGY behavioral protocols (reserved for AGY dev only)
    artifact_vault     – Archived artifacts and documents
"""

from __future__ import annotations

from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Collection Priority Routing
# ═══════════════════════════════════════════════════════════════════════════════

# [FEAT-469] Live operational domains: ground in real lab state.
_LIVE_OPS_PRIORITY = ["feature_dna", "lab_infrastructure", "lab_journal"]

# [FEAT-469] Historical / retrospective domains.
_HISTORICAL_PRIORITY = ["career_ledger", "artifact_vault"]

# Default: all collections eligible.
_DEFAULT_PRIORITY = [
    "feature_dna",
    "lab_infrastructure",
    "lab_journal",
    "career_ledger",
    "behavioral_dna",
    "artifact_vault",
]

# [FEAT-469] Collections strictly suppressed for live operational contexts.
_SUPPRESSED_FOR_LIVE_OPS = {"career_ledger", "behavioral_dna"}


def get_collection_priorities(vibe: str, domain: str) -> list[str]:
    """Return ordered collection priority list for the given vibe/domain pair.

    For ``vibe="META"`` or ``domain="lab_internal"``, returns live-ops
    collections that ground the model in real lab state while suppressing
    career_ledger and behavioral_dna.

    For ``domain="lab_history"``, returns historical collections only.

    All other combinations return the full default list.
    """
    if vibe.upper() == "META" or domain == "lab_internal":
        return list(_LIVE_OPS_PRIORITY)

    if domain == "lab_history":
        return list(_HISTORICAL_PRIORITY)

    return list(_DEFAULT_PRIORITY)


# ═══════════════════════════════════════════════════════════════════════════════
# Zero Context > Default Context
# ═══════════════════════════════════════════════════════════════════════════════

def filter_candidate_context(
    candidates: list[dict[str, Any]],
    vibe: str,
    domain: str,
    max_distance: float = 0.50,
) -> list[dict[str, Any]]:
    """Filter and rank retrieved candidates, enforcing the Zero Context rule.

    If the top candidate's distance exceeds ``max_distance``, the system
    returns an empty list – zero context is preferable to unreliable context
    that could hallucinate false information.

    When vibe is META or domain is lab_internal, candidates from suppressed
    collections (career_ledger, behavioral_dna) are filtered out.

    Candidates are returned sorted by ascending distance (best match first).
    """
    if not candidates:
        return []

    # Sort by distance ascending (best match first)
    sorted_candidates = sorted(candidates, key=lambda c: c.get("distance", 1.0))

    # [FEAT-469] Zero Context gate: if top result exceeds threshold, bail
    top_distance = sorted_candidates[0].get("distance", 1.0)
    if top_distance > max_distance:
        return []

    # [FEAT-469] Live ops suppression
    if vibe.upper() == "META" or domain == "lab_internal":
        sorted_candidates = [
            c
            for c in sorted_candidates
            if c.get("collection") not in _SUPPRESSED_FOR_LIVE_OPS
        ]

    return sorted_candidates


# ═══════════════════════════════════════════════════════════════════════════════
# DNA Tag Formatting
# ═══════════════════════════════════════════════════════════════════════════════

def format_lab_dna_tag(
    coll: str, metadata: dict[str, Any], doc: str
) -> str:
    """Format a candidate document with structured DNA tags.

    Produces tags like ``[FEATURE_DNA: FEAT-469]`` and ``[INFRA: LAB-055]``
    prepended to the document text for structured downstream consumption.

    Returns:
        Formatted string with DNA tag prefix and document body, or the raw
        document text if no applicable tag can be generated.
    """
    tag = _resolve_dna_tag(coll, metadata)

    if tag:
        return f"{tag} {doc}"
    return doc


def _resolve_dna_tag(coll: str, metadata: dict[str, Any]) -> str:
    """Resolve the appropriate DNA tag for a collection/metadata pair.

    Returns:
        Tag string like ``[FEATURE_DNA: FEAT-469]`` or ``[INFRA: LAB-055]``,
        or empty string if no tag applies.
    """
    if coll == "feature_dna":
        feat_id = metadata.get("feature_id", "")
        if feat_id:
            return f"[FEATURE_DNA: {feat_id}]"
        return "[FEATURE_DNA]"

    if coll == "lab_infrastructure":
        component = metadata.get("component", "")
        if component:
            return f"[INFRA: {component}]"
        return "[INFRA]"

    if coll == "behavioral_dna":
        bkm_id = metadata.get("bkm_id", "")
        if bkm_id:
            return f"[BKM: {bkm_id}]"
        return "[BKM]"

    if coll == "career_ledger":
        return "[CAREER]"

    if coll == "artifact_vault":
        return "[ARTIFACT]"

    if coll == "lab_journal":
        return "[JOURNAL]"

    return ""
