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
DEV_LAB_ROOT = BASE_DIR.parent
# Canonical portfolio checkout (mirrors router.py / dna_forge_build.py). Falls back
# to the repo-local copy for hermetic deployments where it is the live checkout.
_canonical_portfolio = DEV_LAB_ROOT / "Portfolio_Dev"
PORTFOLIO_DIR = _canonical_portfolio if _canonical_portfolio.exists() else BASE_DIR / "Portfolio_Dev"
DNA_DIR = PORTFOLIO_DIR / "dna"
DATA_DIR = PORTFOLIO_DIR / "field_notes" / "data"
MANIFEST_PATH = DATA_DIR / "dna_manifest.json"
WISDOM_PATH = DNA_DIR / "wisdom_data.json"
PHILOSOPHY_PATH = DNA_DIR / "philosophy_data.json"
RDNA_PATH = DNA_DIR / "rdna_questions.json"
TIMELINE_PATH = DNA_DIR / "timeline_data.json"
SPRINT_DATA_PATH = DATA_DIR / "sprint_data.json"
PROTOCOLS_PATH = BASE_DIR / "docs" / "Protocols.md"
FEATURE_TRACKER_PATH = PORTFOLIO_DIR / "FeatureTracker.md"
BONE_COLLECTIONS_PATH = DATA_DIR / "bone_collections.json"
BONES_DIR = DATA_DIR / "bones"
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
        resp = requests.post(vllm_url, json=payload, timeout=120)
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


def _read_json_safe(path: Path) -> Any:
    """[STORY 86.9] Read any JSON source file; returns [] on absence or parse failure."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _max_numeric_id(entries: Any, prefix: str) -> int:
    """[STORY 86.9] Highest integer suffix among entries whose id matches f"{prefix}-\\d+". Returns 0 if none."""
    if isinstance(entries, dict):
        entries = entries.get("cards", [])
    max_num = 0
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("id", "") or "")
        m = re.search(rf"\b{re.escape(prefix)}-(\d+)", eid)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num


def _max_markdown_id(md_path: Path, prefix: str) -> int:
    """[STORY 86.9] Highest f"{prefix}-\\d+" occurrence found in a Markdown source file. Returns 0 if unreadable."""
    if not md_path.exists():
        return 0
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0
    return max((int(n) for n in re.findall(rf"\b{re.escape(prefix)}-(\d+)", text)), default=0)


def _domain_source_max_id(dom: str) -> int:
    """
    [STORY 86.9] Maximum existing numeric ID for a domain from its authoritative
    source of truth, so draft promotion can never collide with foundational cards:
      - BKM   -> HomeLabAI/docs/Protocols.md              (matching BKM-\\d+)
      - FEAT  -> Portfolio_Dev/FeatureTracker.md          (matching FEAT-\\d+)
      - RDNA  -> Portfolio_Dev/dna/rdna_questions.json    (ids matching RDNA-\\d+)
      - DISC  -> Portfolio_Dev/dna/timeline_data.json     (ids matching DISC-\\d+)
    Domains without a dedicated source (SPRINT, ...) return 0 and fall back to
    manifest-scan only.
    """
    if dom == "BKM":
        return _max_markdown_id(PROTOCOLS_PATH, "BKM")
    if dom == "FEAT":
        return _max_markdown_id(FEATURE_TRACKER_PATH, "FEAT")
    if dom == "RDNA":
        return _max_numeric_id(_read_json_safe(RDNA_PATH), "RDNA")
    if dom == "DISC":
        return _max_numeric_id(_read_json_safe(TIMELINE_PATH), "DISC")
    return 0


def _trigger_static_html_rebuild(created_cards: List[Dict[str, Any]]) -> None:
    """
    [STORY 86.7] Fire-and-forget background rebuild of static HTML generators so
    newly promoted draft cards appear immediately without manual intervention:
      - dna_forge_build.py: aggregates BKM/FEAT/RDNA/DISC/SPRINT into dna_forge.html
      - wisdom_build.py:    regenerates wisdom.html whenever WIS/PHL cards were promoted
    Never blocks or fails the promotion transaction.
    """
    if not created_cards:
        return
    try:
        import subprocess
        import sys
    except Exception:
        return
    build_dir = PORTFOLIO_DIR / "field_notes"
    scripts = ["dna_forge_build.py"]
    domains = {str(c.get("domain", "")).upper() for c in created_cards}
    if domains & {"WIS", "PHL"}:
        scripts.append("wisdom_build.py")
    for script in scripts:
        script_path = build_dir / script
        if not script_path.exists():
            continue
        try:
            subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(build_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            # A failed rebuild must never roll back an already-persisted promotion.
            continue


def promote_draft_to_db(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    [FEAT-597 / BKM-022 / BKM-041]
    Promotes validated draft chunks into permanent sovereign DNA cards
    in Portfolio_Dev/dna/*.json, dna_manifest.json, and ChromaDB (:8001).
    """
    try:
        from infra.atomic_io import atomic_write_json
    except ImportError:
        def atomic_write_json(path, data, indent=2):
            import tempfile, os
            dir_name = os.path.dirname(os.path.abspath(path))
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                json.dump(data, tf, indent=indent)
                temp_name = tf.name
            os.replace(temp_name, path)

    chunks = payload.get("chunks", [])
    bone_col = payload.get("suggested_bone_collection") or {}
    
    # Load manifest and domain source files
    manifest = {}
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    wisdom_cards = []
    if WISDOM_PATH.exists():
        try:
            with open(WISDOM_PATH, "r", encoding="utf-8") as f:
                wisdom_cards = json.load(f)
        except Exception:
            wisdom_cards = []

    philosophy_cards = []
    if PHILOSOPHY_PATH.exists():
        try:
            with open(PHILOSOPHY_PATH, "r", encoding="utf-8") as f:
                philosophy_cards = json.load(f)
        except Exception:
            philosophy_cards = []

    created_cards = []
    created_bone_items = []
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Chroma client for atomic sync
    chroma_client = None
    try:
        import chromadb
        chroma_client = chromadb.HttpClient(host="127.0.0.1", port=8001)
    except Exception:
        chroma_client = None

    wisdom_modified = False
    philosophy_modified = False

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

        # Determine next ID accurately from source of truth
        if dom == "WIS":
            nums = [int(re.search(r'\d+', card.get("id", "0")).group()) for card in wisdom_cards if re.search(r'\d+', card.get("id", "0"))]
            next_num = max(nums, default=0) + 1
        elif dom == "PHL":
            nums = [int(re.search(r'\d+', card.get("id", "0")).group()) for card in philosophy_cards if re.search(r'\d+', card.get("id", "0"))]
            next_num = max(nums, default=0) + 1
        else:
            # [STORY 86.9] Lift the ID floor from the authoritative domain source
            # file(s) (Protocols.md / FeatureTracker.md / rdna_questions.json /
            # timeline_data.json) so an empty or gapped manifest can never collide
            # with foundational IDs (e.g. BKM-001) on draft card promotion.
            existing_col = manifest.get(col_key, [])
            nums = [int(re.search(r'\d+', card.get("id", "0")).group()) for card in existing_col if re.search(r'\d+', card.get("id", "0"))]
            source_max = _domain_source_max_id(dom)
            next_num = max(max(nums, default=0), source_max) + 1

        new_id = f"{dom}-{next_num:03d}"

        new_card = {
            "id": new_id,
            "domain": dom,
            "theme": c.get("theme") or ("Memory & JITC" if dom == "PHL" else "Systems Architecture & Automation"),
            "paper_order": next_num,
            "origin": {
                "author": c.get("author") or "jallred",
                "text": c.get("origin_verbatim", ""),
                "source": "Drafting Studio Promotion",
                "immutable": True,
                "created_at": timestamp
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
                "explicit_links": [],
                "status": "APPROVED",
                "bucket_id": "bucket_1_jitc" if dom == "PHL" else "bucket_architecture"
            }
        }

        # Update specific domain file array
        if dom == "WIS":
            wisdom_cards.append(new_card)
            wisdom_modified = True
        elif dom == "PHL":
            philosophy_cards.append(new_card)
            philosophy_modified = True

        # Update manifest
        if col_key not in manifest:
            manifest[col_key] = []
        manifest[col_key].append(new_card)

        # Sync to ChromaDB collection
        if chroma_client:
            try:
                target_col_name = "philosophy_dna" if dom == "PHL" else "wisdom_dna"
                col = chroma_client.get_or_create_collection(target_col_name)
                doc_text = f"ID: {new_id}\nTitle: {new_card['synthesis']['title']}\nSynthesis: {new_card['synthesis']['narrative_context']}"
                col.upsert(
                    ids=[new_id],
                    documents=[doc_text],
                    metadatas=[{
                        "id": new_id,
                        "title": new_card["synthesis"]["title"],
                        "theme": new_card["theme"],
                        "type": "PHILOSOPHY" if dom == "PHL" else "WISDOM",
                        "tags": ",".join(new_card["metadata"]["tags"])
                    }]
                )
            except Exception as ce:
                pass

        created_cards.append(new_card)
        created_bone_items.append({
            "id": new_id,
            "title": new_card["synthesis"]["title"],
            "domain": dom
        })

    # Atomically persist domain files
    if wisdom_modified:
        WISDOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(str(WISDOM_PATH), wisdom_cards)

    if philosophy_modified:
        PHILOSOPHY_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(str(PHILOSOPHY_PATH), philosophy_cards)

    # Atomically persist manifest
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(str(MANIFEST_PATH), manifest)

    # Save bone collection if provided
    created_collection_id = None
    if bone_col and created_bone_items:
        col_name = bone_col.get("name") or "Promoted Track Collection"
        created_collection_id = f"bone_{col_name.lower().replace(' ', '_').replace(':', '').replace('-', '_')}"
        
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

        atomic_write_json(str(BONE_COLLECTIONS_PATH), bone_cols)

        # [FEAT-601] Save 1:1 Source Bone Collection scratchpad
        slug = col_name.lower().replace(" ", "_").replace(":", "").replace("-", "_")
        BONES_DIR.mkdir(parents=True, exist_ok=True)
        source_bones_path = BONES_DIR / f"{slug}_bones.json"
        source_bone_data = {
            "id": created_collection_id,
            "name": col_name,
            "theme": bone_col.get("theme", "Systems Architecture & Automation"),
            "created_at": timestamp,
            "updated_at": timestamp,
            "bones": [
                {
                    "sequence": idx + 1,
                    "id": c.get("id"),
                    "domain": c.get("domain", "WIS"),
                    "title": c.get("synthesis", {}).get("title"),
                    "origin_verbatim": c.get("origin", {}).get("text"),
                    "revisions": c.get("synthesis", {}).get("revisions", []),
                    "mutations": c.get("synthesis", {}).get("mutations", [])
                }
                for idx, c in enumerate(created_cards)
            ]
        }
        atomic_write_json(str(source_bones_path), source_bone_data)

    # [STORY 86.7] Background rebuild of static HTML so newly promoted cards
    # appear immediately in dna_forge.html / wisdom.html without manual builds.
    if created_cards:
        _trigger_static_html_rebuild(created_cards)

    return {
        "status": "success",
        "promoted_count": len(created_cards),
        "created_ids": [c["id"] for c in created_cards],
        "created_collection_id": created_collection_id,
        "timestamp": timestamp
    }
