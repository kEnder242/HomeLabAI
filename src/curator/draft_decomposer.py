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


def decompose_draft(raw_text: str, custom_title: str = None) -> Dict[str, Any]:
    """
    [FEAT-597 / BKM-024 / PHL-035]
    Pure Live Silicon DNA Decomposer.
    Decomposes unstructured stream-of-consciousness text into polymorphic DNA pearls
    via live resident vLLM on RTX 2080 Ti (port 8088).
    
    INVARIANT: Fail-fast if live vLLM is unreachable or generation fails. Zero regex fallbacks.
    """
    cleaned = raw_text.strip()
    if not cleaned:
        return {
            "title": "Empty Note",
            "summary": "No content provided.",
            "chunks": [],
            "suggested_bone_collection": {"name": "Empty Draft Scaffold", "bones": []}
        }

    # Extract author-specified header if present
    if not custom_title:
        first_line = cleaned.split("\n")[0].strip()
        if first_line.startswith("#"):
            custom_title = first_line.lstrip("#").strip()

    import requests

    vllm_url = "http://127.0.0.1:8088/v1/chat/completions"
    
    system_prompt = (
        "You are the Sovereign Federated Lab DNA Decomposer and Knowledge Architect.\n"
        "Your task is to decompose raw engineering notes, retrospective logs, or architectural stream-of-consciousness "
        "into discrete, atomic, high-signal DNA pearls.\n\n"
        "DNA DOMAIN TAXONOMY (Strictly assign one per chunk):\n"
        "- 'BKM': Best Known Method / Hard Invariant / Operational Rule / Protocol Mandate\n"
        "- 'PHL': Philosophical Axiom / Guiding North Star / First Principle\n"
        "- 'WIS': Hard-Won Wisdom / Battle Scars / Post-Mortem Insight\n"
        "- 'FEAT': System Capability / Technical Feature / Architecture Subsystem\n"
        "- 'DISC': Breakthrough Discovery / Benchmark Finding / Research Milestone\n"
        "- 'RDNA': Reverse DNA / Inverted Inquiry / Diagnostic Question Anchor\n"
        "- 'SPRINT': Agile Cadence / Execution Horizon / Story Packaging\n\n"
        "RESPONSE FORMAT:\n"
        "You MUST respond with valid JSON ONLY (enclosed in ```json ... ``` or raw JSON) matching this exact schema:\n"
        "{\n"
        '  "title": "Synthesized Synthesis Title",\n'
        '  "summary": "1-2 sentence overarching summary of the decomposed pearls",\n'
        '  "chunks": [\n'
        "    {\n"
        '      "chunk_id": "CHUNK-01",\n'
        '      "proposed_domain": "BKM|PHL|WIS|FEAT|DISC|RDNA|SPRINT",\n'
        '      "title": "Punchy Atomic Title (max 60 chars)",\n'
        '      "narrative": "Crisp, synthesized explanation of this single pearl",\n'
        '      "origin_verbatim": "Exact source text snippet this was extracted from",\n'
        '      "suggested_tags": ["tag1", "tag2"],\n'
        '      "mutations": [\n'
        '        {"id": "mut_active", "lens": "Active Voice", "text": "Active first-person engineering statement."},\n'
        '        {"id": "mut_recruiter", "lens": "Executive / STAR", "text": "Executive impact statement."}\n'
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "suggested_bone_collection": {\n'
        '    "name": "Track: <Title>",\n'
        '    "bones": [\n'
        '      {"id": "CHUNK-01", "title": "<Title>", "domain": "<DOMAIN>"}\n'
        "    ]\n"
        "  }\n"
        "}"
    )

    user_prompt = f"Decompose the following text into atomic DNA pearls:\n\n{cleaned}"
    if custom_title:
        user_prompt = f"Target Title: {custom_title}\n\n" + user_prompt

    payload = {
        "model": "local-unified-base",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.15,
        "max_tokens": 2048
    }

    try:
        resp = requests.post(vllm_url, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"vLLM returned HTTP {resp.status_code}: {resp.text}")
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        # Strict BKM-024 Invariant: Do NOT mask with regex. Fail fast.
        raise RuntimeError(f"[BKM-024] Live Silicon Decomposition Failed on vLLM (port 8088): {e}") from e

    # Parse JSON from model output
    cleaned_json = content.strip()
    if "```json" in cleaned_json:
        cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned_json:
        cleaned_json = cleaned_json.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(cleaned_json)
    except Exception as e:
        raise RuntimeError(f"[BKM-024] vLLM generated invalid JSON structure: {e}\nRaw Output: {content[:300]}") from e

    # Validate schema basics
    if not isinstance(parsed, dict) or "chunks" not in parsed:
        raise RuntimeError(f"[BKM-024] vLLM output missing 'chunks' array. Raw: {content[:300]}")

    if custom_title:
        parsed["title"] = custom_title
        if "suggested_bone_collection" in parsed:
            parsed["suggested_bone_collection"]["name"] = f"Track: {custom_title}"

    # Ensure chunk_ids and index consistency
    for idx, c in enumerate(parsed.get("chunks", []), 1):
        c["chunk_id"] = f"CHUNK-{idx:02d}"
        c["proposed_domain"] = str(c.get("proposed_domain") or "WIS").upper()
        if c["proposed_domain"] not in ["PHL", "WIS", "BKM", "FEAT", "DISC", "RDNA", "SPRINT"]:
            c["proposed_domain"] = "WIS"
        if not c.get("origin_verbatim"):
            c["origin_verbatim"] = c.get("narrative", "")
        if not c.get("suggested_tags"):
            c["suggested_tags"] = [c["proposed_domain"].lower()]
        if not c.get("mutations"):
            c["mutations"] = [
                {"id": f"mut_{idx}_active", "lens": "Active Voice", "text": f"Enforces {c.get('title','').lower()} with zero latency."},
                {"id": f"mut_{idx}_recruiter", "lens": "Executive / STAR", "text": f"Architected and governed {c.get('title','').lower()}."}
            ]

    # Sync suggested bones
    if "suggested_bone_collection" not in parsed or not parsed["suggested_bone_collection"]:
        parsed["suggested_bone_collection"] = {
            "name": f"Track: {parsed.get('title', 'Synthesis Draft')}",
            "bones": [
                {"id": c["chunk_id"], "title": c["title"], "domain": c["proposed_domain"]}
                for c in parsed.get("chunks", [])
            ]
        }
    else:
        parsed["suggested_bone_collection"]["bones"] = [
            {"id": c["chunk_id"], "title": c["title"], "domain": c["proposed_domain"]}
            for c in parsed.get("chunks", [])
        ]

    return parsed


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
