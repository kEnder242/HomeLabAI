#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
draft_decomposer.py
[FEAT-597 / FEAT-598]
Draft Ingestion, Semantic Chunk Decomposition, DNA Domain Classifier & Bone Suggestion Engine.
"""

import json
import re
import time
import datetime
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PORTFOLIO_DIR = BASE_DIR / "Portfolio_Dev"
DATA_DIR = PORTFOLIO_DIR / "field_notes" / "data"
MANIFEST_PATH = DATA_DIR / "dna_manifest.json"
WISDOM_PATH = DATA_DIR / "wisdom_data.json"
PHILOSOPHY_PATH = DATA_DIR / "philosophy_data.json"
BONE_COLLECTIONS_PATH = DATA_DIR / "bone_collections.json"
CONNECTIONS_GRAPH_PATH = DATA_DIR / "dna_connections_graph.json"


def infer_domain(text: str) -> str:
    """Classifies a semantic chunk into the most appropriate DNA domain."""
    t = text.lower()
    if any(k in t for k in ["rule", "protocol", "mandate", "bkm", "must always", "invariant", "never propose", "strictly"]):
        return "BKM"
    if any(k in t for k in ["axiom", "philosophy", "phl", "paradigm", "first principle", "belief", "mental model"]):
        return "PHL"
    if any(k in t for k in ["feat-", "feature", "capability", "endpoint", "architecture", "engine", "service", "system"]):
        return "FEAT"
    if any(k in t for k in ["discovery", "timeline", "milestone", "breakthrough", "eureka", "found that"]):
        return "DISC"
    if any(k in t for k in ["sprint", "story", "ladder", "backlog"]):
        return "SPRINT"
    if any(k in t for k in ["question", "how do we", "what is", "why does"]):
        return "RDNA"
    return "WIS"


def decompose_draft(raw_text: str, custom_title: str = None) -> Dict[str, Any]:
    """
    Decomposes unstructured notes into:
    - Extracted / generated Title & Summary
    - Paragraph-level semantic chunks classified by DNA domain
    - Suggested Bone Collection skeleton tying the chunks together
    """
    cleaned = raw_text.strip()
    if not cleaned:
        return {
            "title": "Empty Note",
            "summary": "No content provided.",
            "chunks": [],
            "suggested_bone_collection": {"name": "Empty Draft Scaffold", "bones": []}
        }

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

    # Extract title
    title = custom_title
    if not title:
        first_line = lines[0] if lines else "Untitled Synthesis Draft"
        if first_line.startswith("#"):
            title = first_line.lstrip("#").strip()
        elif len(first_line) < 80:
            title = first_line
        else:
            title = first_line[:60].strip() + "..."

    # Split into paragraph chunks (group lines separated by blank lines or headers)
    raw_paragraphs = re.split(r'\n\s*\n', cleaned)
    chunks = []
    chunk_idx = 1

    for p in raw_paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        # If this chunk starts with top title header, strip the heading line
        if p_clean.startswith("#") and "\n" in p_clean:
            p_lines = p_clean.split("\n")
            p_clean = "\n".join(p_lines[1:]).strip()
            if not p_clean:
                continue
        elif p_clean.startswith("#") and not ("\n" in p_clean) and len(raw_paragraphs) > 1:
            continue

        domain = infer_domain(p_clean)
        
        # Extract chunk title
        p_lines = [l.strip() for l in p_clean.split("\n") if l.strip()]
        first_p_line = p_lines[0] if p_lines else f"Chunk {chunk_idx}"
        if first_p_line.startswith("#") or first_p_line.startswith("- **") or first_p_line.startswith("**"):
            c_title = re.sub(r'^[#\-\*\s]+', '', first_p_line).split(":")[0].strip()
        else:
            c_title = (first_p_line[:50] + "...") if len(first_p_line) > 50 else first_p_line

        # Auto-extract tags
        words = set(re.findall(r'\b[A-Za-z0-9_-]{4,15}\b', p_clean.lower()))
        sample_tags = []
        for w in ["architecture", "vector", "triage", "silicon", "gpu", "testing", "resume", "lens", "memory", "synapse", "cache", "protocol", "synthesis"]:
            if w in words:
                sample_tags.append(w)
        if not sample_tags:
            sample_tags = [domain.lower()]

        # Generate sample mutations (Voice Vector proposals)
        mutations = [
            {
                "id": f"mut_{chunk_idx}_active",
                "lens": "Active Voice / High Energy",
                "text": f"Enforces {c_title.lower()} across operational pipelines with zero latency."
            },
            {
                "id": f"mut_{chunk_idx}_recruiter",
                "lens": "Executive Recruiter / Impact",
                "text": f"Architected and deployed {c_title.lower()}, accelerating synthesis speed and governance."
            }
        ]

        chunks.append({
            "chunk_id": f"CHUNK-{chunk_idx:02d}",
            "proposed_domain": domain,
            "title": c_title,
            "narrative": p_clean,
            "origin_verbatim": p_clean,
            "suggested_tags": sample_tags,
            "mutations": mutations,
            "active_revision": None
        })
        chunk_idx += 1

    # Suggested Bone Collection Skeleton
    bone_name = f"Track: {title}"
    suggested_bones = [
        {"id": c["chunk_id"], "title": c["title"], "domain": c["proposed_domain"]}
        for c in chunks
    ]

    return {
        "title": title,
        "summary": f"Decomposed {len(chunks)} discrete semantic units across {len(set(c['proposed_domain'] for c in chunks))} domains.",
        "chunks": chunks,
        "suggested_bone_collection": {
            "name": bone_name,
            "bones": suggested_bones
        }
    }


def promote_draft_to_db(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Promotes validated draft chunks into permanent sovereign DNA cards
    in data/dna_manifest.json and ChromaDB.
    """
    chunks = payload.get("chunks", [])
    bone_col = payload.get("suggested_bone_collection") or {}
    
    # Load manifest
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    created_cards = []
    created_bone_items = []
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Determine highest ID per collection
    for c in chunks:
        dom = c.get("proposed_domain", "WIS").upper()
        col_key = {
            "WIS": "wisdom",
            "PHL": "philosophy",
            "BKM": "behavioral",
            "FEAT": "feature",
            "SPRINT": "sprint",
            "DISC": "discovery",
            "RDNA": "rdna"
        }.get(dom, "wisdom")

        existing_col = manifest.get(col_key, [])
        next_num = len(existing_col) + 1
        new_id = f"{dom}-{next_num:03d}"

        new_card = {
            "id": new_id,
            "domain": dom,
            "title": c.get("title") or f"{dom} Artifact {next_num}",
            "status": "APPROVED",
            "origin": {
                "text": c.get("origin_verbatim", ""),
                "source": "Drafting Studio Promotion",
                "timestamp": timestamp
            },
            "synthesis": {
                "title": c.get("title") or f"{dom} Artifact {next_num}",
                "narrative_context": c.get("narrative", ""),
                "lab_anchors": [],
                "tags": c.get("suggested_tags", [dom.lower()]),
                "mutations": c.get("mutations", []),
                "revisions": [
                    {
                        "id": f"rev_{new_id}_v1",
                        "text": c.get("narrative", ""),
                        "lens": "Original Baseline",
                        "certified_by": "operator",
                        "timestamp": timestamp
                    }
                ]
            },
            "metadata": {
                "tags": c.get("suggested_tags", [dom.lower()]),
                "status": "APPROVED",
                "promoted_from_draft": True
            }
        }

        if col_key not in manifest:
            manifest[col_key] = []
        manifest[col_key].append(new_card)

        created_cards.append(new_card)
        created_bone_items.append({
            "id": new_id,
            "title": new_card["title"],
            "domain": dom
        })

    # Save manifest
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Save bone collection if provided
    created_collection_id = None
    if bone_col and created_bone_items:
        col_name = bone_col.get("name") or "Promoted Track Collection"
        created_collection_id = f"bone_{col_name.lower().replace(' ', '_').replace(':', '')}"
        
        bone_cols = []
        if BONE_COLLECTIONS_PATH.exists():
            try:
                with open(BONE_COLLECTIONS_PATH, "r", encoding="utf-8") as f:
                    bone_cols = json.load(f)
            except Exception:
                bone_cols = []

        bone_cols.append({
            "id": created_collection_id,
            "name": col_name,
            "bones": created_bone_items,
            "created_at": timestamp
        })

        with open(BONE_COLLECTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(bone_cols, f, indent=2)

    return {
        "status": "success",
        "promoted_count": len(created_cards),
        "created_ids": [c["id"] for c in created_cards],
        "created_collection_id": created_collection_id,
        "timestamp": timestamp
    }
