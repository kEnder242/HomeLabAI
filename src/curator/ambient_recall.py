#!/usr/bin/env python3
"""[FEAT-600 / LAB-019] Resident Ambient Memory & Knowledge Recall Module.

Runs within resident memory (e.g. Foyer :8765 or CLaRa-DNA).
Executes turn-gated, dynamic distance-banded semantic recall against ChromaDB
collections (behavioral_dna, feature_dna, philosophy_dna, sprint_dna) and ICM,
returning structured prompt injections and single-line badge breadcrumbs.
"""

import json
import logging
import os
import re
import subprocess
import time

logger = logging.getLogger("ambient_recall")

# ChromaDB & Model Shared State in Daemon
_chroma_client = None
_embedding_model = None

CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")

SHALLOW_PROMPTS = {
    "hi", "hello", "hey", "yes", "no", "y", "n", "ok", "okay", "sure", "thanks", "thank you",
    "proceed", "continue", "go ahead", "run it", "do it", "looks good", "status"
}

LIST_PATTERN = re.compile(
    r'(?:^|\n|\s+)'
    r'(?:'
        r'(\d+)[\)\.]|'
        r'\[(\d+)\]|'
        r'\((\d+)\)|'
        r'(?<![a-zA-Z0-9])([a-zA-Z])[\)\.]'
    r')\s+'
)

_SPRINT_KEYWORD_RE = re.compile(
    r"\b(?:SPR(?:INT)?[-_ ]?\d+|Story\s+\d+\.\d+|sprint_dna)\b|\bsprint\b|\bplan\b|\bretro\b",
    re.IGNORECASE,
)


def get_chroma_client():
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client
    try:
        import chromadb
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        client.heartbeat()
        _chroma_client = client
        return _chroma_client
    except Exception as e:
        logger.warning(f"HttpClient connection failed: {e}. Falling back to PersistentClient.")
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=DB_PATH)
            return _chroma_client
        except Exception:
            return None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model if _embedding_model is not False else None
    try:
        from fastembed import TextEmbedding
        _embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        _embedding_model = False
    return _embedding_model if _embedding_model is not False else None


def clean_prompt(text: str) -> str:
    cleaned = re.sub(r"<SYSTEM_MESSAGE>.*?</SYSTEM_MESSAGE>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<.*?>", "", cleaned)
    cleaned = re.sub(r"^\[Message\].*?content=", "", cleaned)
    return cleaned.strip()


def extract_prompt_segments(cleaned: str) -> list[dict]:
    if not cleaned:
        return []
    matches = list(LIST_PATTERN.finditer(cleaned))
    if len(matches) < 2:
        bullet_matches = list(re.finditer(r'(?:^|\n)\s*[-*]\s+', cleaned))
        if len(bullet_matches) >= 2:
            segments = []
            for i, bm in enumerate(bullet_matches):
                start = bm.end()
                end = bullet_matches[i + 1].start() if i + 1 < len(bullet_matches) else len(cleaned)
                seg_text = cleaned[start:end].strip()
                if seg_text:
                    segments.append({'id': f'bullet_{i+1}', 'label': f'Bullet {i+1}', 'text': seg_text})
            return segments
        return [{'id': '1', 'label': 'Query', 'text': cleaned}]

    segments = []
    preamble = cleaned[:matches[0].start()].strip()
    if preamble and len(preamble.split()) >= 3:
        segments.append({'id': '0', 'label': 'Context', 'text': preamble})

    for i, m in enumerate(matches):
        marker_id = m.group(1) or m.group(2) or m.group(3) or m.group(4) or str(i + 1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        seg_text = cleaned[start:end].strip()
        if seg_text:
            segments.append({'id': marker_id, 'label': f'Item {marker_id}', 'text': seg_text})

    return segments if segments else [{'id': '1', 'label': 'Query', 'text': cleaned}]


def extract_literal_ids(text: str) -> list[str]:
    results = []
    bkms = re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE)
    feats = re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE)
    labs = re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE)
    wis = re.findall(r"\b(WIS-\d{3}|PHL-\d{3})\b", text, re.IGNORECASE)
    sprs = re.findall(r"\b(SPR(?:INT)?[-_ ]?\d+(?:\.\d+)?)\b", text, re.IGNORECASE)

    for b in sorted(set(bkms)):
        results.append(f"- [{b.upper()}] (Literal Protocol Anchor)")
    for f in sorted(set(feats)):
        results.append(f"- [{f.upper()}] (Literal Feature Anchor)")
    for l in sorted(set(labs)):
        results.append(f"- [{l.upper()}] (Literal Lab Anchor)")
    for w in sorted(set(wis)):
        results.append(f"- [{w.upper()}] (Literal Philosophy Anchor)")
    for s in sorted(set(sprs)):
        results.append(f"- [{s.upper()}] (Literal Sprint Anchor)")
    return results


def is_turn_start(transcript_path: str) -> tuple[bool, str]:
    """Inspects transcript history to verify this is the start of a user turn."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False, ""
    last_event_type = None
    last_user_prompt = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    rec_type = record.get("type")
                    if rec_type:
                        last_event_type = rec_type
                    if rec_type == "USER_INPUT":
                        last_user_prompt = record.get("content", "")
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error reading transcript {transcript_path}: {e}")
        return False, ""

    # Gating rule: Only run ambient recall if the immediate previous transcript record was USER_INPUT
    return (last_event_type == "USER_INPUT"), last_user_prompt


def probe_claradb(text: str, client, model, is_qq: bool = False, limit: int = 4, seen_ids: set = None) -> list[str]:
    results = []
    if seen_ids is None:
        seen_ids = set()

    bkms = re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE)
    feats = re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE)
    labs = re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE)

    if not client:
        return extract_literal_ids(text)

    try:
        if bkms:
            col_bkm = client.get_collection("behavioral_dna")
            for b in bkms:
                b_up = b.upper()
                if b_up in seen_ids:
                    continue
                r = col_bkm.get(where={"bkm_id": b_up})
                if r and r.get("metadatas"):
                    seen_ids.add(b_up)
                    meta = r["metadatas"][0]
                    results.append(f"- [{b_up}] {meta.get('name', 'Protocol')}")

        if feats:
            col_feat = client.get_collection("feature_dna")
            for f in feats:
                f_up = f.upper()
                if f_up in seen_ids:
                    continue
                r = col_feat.get(where={"feature_id": f_up})
                if r and r.get("metadatas"):
                    seen_ids.add(f_up)
                    meta = r["metadatas"][0]
                    status = meta.get("status", "ACTIVE")
                    results.append(f"- [{f_up}] {meta.get('name', 'Feature')} ({status})")

        if labs:
            col_bkm = client.get_collection("behavioral_dna")
            all_infra = col_bkm.get(where={"type": "INFRA"})
            if all_infra and all_infra.get("metadatas"):
                for l in labs:
                    l_target = l.upper()
                    if l_target in seen_ids:
                        continue
                    for meta in all_infra["metadatas"]:
                        name = meta.get("name", "")
                        if l_target in name.upper():
                            seen_ids.add(l_target)
                            results.append(f"- [{l_target}] {name}")
                            break

        words = set(re.findall(r"\w+", text.lower()))
        significant_words = {w for w in words if len(w) > 2 and w not in SHALLOW_PROMPTS}

        if model and len(significant_words) >= 1 and len(results) < limit:
            emb = list(model.embed([text[:200]]))[0].tolist()

            col_feat = client.get_collection("feature_dna")
            r_feat = col_feat.query(query_embeddings=[emb], n_results=min(limit + 2, 6))
            feat_dists = r_feat.get("distances", [[]])[0]
            if feat_dists:
                min_feat_dist = min(feat_dists)
                for i, dist in enumerate(feat_dists):
                    if len(results) >= limit:
                        break
                    meta = r_feat["metadatas"][0][i]
                    name = meta.get("name", "Feature")
                    fid = meta.get("feature_id") or r_feat["ids"][0][i].split("_")[0]
                    status = meta.get("status", "ACTIVE")
                    if fid in seen_ids:
                        continue
                    has_kw = any(w in name.lower() for w in significant_words)
                    is_in_band = (dist <= 0.55) or (dist <= min_feat_dist + 0.10 and dist < 0.62) or (has_kw and dist <= 0.60)
                    if is_qq:
                        is_in_band = is_in_band or (dist <= 0.60)
                    if is_in_band:
                        seen_ids.add(fid)
                        results.append(f"- [{fid}] {name} ({status})")

            if len(results) < limit:
                col_bkm = client.get_collection("behavioral_dna")
                r_bkm = col_bkm.query(query_embeddings=[emb], n_results=min(limit + 1, 4))
                bkm_dists = r_bkm.get("distances", [[]])[0]
                if bkm_dists:
                    min_bkm_dist = min(bkm_dists)
                    for i, dist in enumerate(bkm_dists):
                        if len(results) >= limit:
                            break
                        meta = r_bkm["metadatas"][0][i]
                        name = meta.get("name", "Protocol")
                        bkm_id = meta.get("bkm_id")
                        if bkm_id and bkm_id in seen_ids:
                            continue
                        has_kw = any(w in name.lower() for w in significant_words)
                        is_in_band = (dist <= 0.55) or (dist <= min_bkm_dist + 0.10 and dist < 0.62) or (has_kw and dist <= 0.60)
                        if is_qq:
                            is_in_band = is_in_band or (dist <= 0.60)
                        if is_in_band:
                            if bkm_id:
                                seen_ids.add(bkm_id)
                                results.append(f"- [{bkm_id}] {name}")
                            else:
                                results.append(f"- {name}")
    except Exception as e:
        logger.error(f"Error in probe_claradb: {e}")
    return results


def probe_sprint_dna(text: str, client, limit: int = 2, seen_ids: set = None) -> list[str]:
    if not bool(_SPRINT_KEYWORD_RE.search(text)):
        return []
    if seen_ids is None:
        seen_ids = set()
    if not client:
        return []
    try:
        col = client.get_collection("sprint_dna")
        res = col.query(query_texts=[text[:500]], n_results=limit)
        results = []
        metas = (res.get("metadatas") or [[]])[0] or []
        docs = (res.get("documents") or [[]])[0] or []
        ids = (res.get("ids") or [[]])[0] or []
        for i, meta in enumerate(metas):
            sprint_id = meta.get("sprint_id", ids[i][:14] if i < len(ids) else "SPR")
            if sprint_id in seen_ids:
                continue
            weight = meta.get("recency", 0.0)
            level = meta.get("level", 2)
            kind = meta.get("kind", "overview")
            snippet = ""
            if i < len(docs) and docs[i]:
                snippet = next(
                    (ln.strip() for ln in docs[i].splitlines()
                     if ln.strip() and not ln.startswith("STORY") and not ln.startswith("SPRINT")),
                    ""
                )[:60]
            line = f"- [sprint_dna:{sprint_id}] L{level} {kind} (w={weight:.2f})"
            if snippet:
                line += f" — {snippet}"
            seen_ids.add(sprint_id)
            results.append(line)
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        logger.warning(f"sprint_dna probe failed: {e}")
        return []


def probe_icm(text: str, project: str, is_qq: bool = False, limit: int = 2) -> list[str]:
    words = text.lower().split()
    if len(words) < 2 or text.lower() in SHALLOW_PROMPTS:
        return []
    score_threshold = 0.40 if is_qq else 0.45
    try:
        res = subprocess.run(
            ["icm", "recall", text[:200], "-f", "json", "-l", str(limit), "-p", project],
            capture_output=True,
            text=True,
            timeout=4
        )
        if res.returncode == 0 and res.stdout.strip():
            memories = json.loads(res.stdout)
            strong = [m for m in memories if m.get("score", 0) >= score_threshold]
            return [f"- ({m.get('topic')}) {m.get('summary')}" for m in strong]
    except Exception as e:
        logger.warning(f"icm recall failed: {e}")
    return []


def execute_ambient_recall(payload: dict) -> dict:
    """Core entry point for ambient recall executed in resident daemon."""
    t_start = time.time()
    agent_name = (payload.get("agent") or payload.get("agentName") or "").lower()
    session_title = (payload.get("sessionTitle") or payload.get("title") or "").lower()
    user_input_raw = (payload.get("userMessage") or payload.get("prompt") or payload.get("last_user_message") or "")

    # 1. Delegation Bypass Guard
    if ("junior" in agent_name or "junior" in session_title or "air" in agent_name or
            any(marker in user_input_raw for marker in ["[STORY DELEGATION TARGET", "[TASK:", "[ORCHESTRATION INSTRUCTIONS", "[SPOON-FED TASK", "[MOMUS:", "[LIBRARIAN:"])):
        return {"injectSteps": [], "meta": {"status": "BYPASSED_DELEGATION", "duration_ms": round((time.time() - t_start) * 1000, 2)}}

    # 2. Turn-Boundary Gating Guard
    inv_num = payload.get("invocationNum", 1)
    transcript_path = payload.get("transcriptPath")
    workspace_paths = payload.get("workspacePaths", [])
    project = os.path.basename(workspace_paths[0]) if workspace_paths else "Dev_Lab"

    # For inv_num > 1, enforce that the last event in transcript was USER_INPUT
    if inv_num > 1:
        is_start, last_prompt = is_turn_start(transcript_path)
        if not is_start:
            # Internal agent tool step: exit immediately in <1ms
            return {"injectSteps": [], "meta": {"status": "SKIPPED_TOOL_LOOP", "duration_ms": round((time.time() - t_start) * 1000, 2)}}
        cleaned = clean_prompt(last_prompt)
    else:
        # Session start
        cleaned = clean_prompt(user_input_raw)

    if not cleaned:
        return {"injectSteps": [], "meta": {"status": "EMPTY_PROMPT", "duration_ms": round((time.time() - t_start) * 1000, 2)}}

    # 3. Execute Vector Grounding
    client = get_chroma_client()
    model = get_embedding_model()

    is_qq = bool(re.match(r"^qq\b", cleaned, re.IGNORECASE))
    search_query = re.sub(r"^qq[:\s]*", "", cleaned, flags=re.IGNORECASE).strip()
    segments = extract_prompt_segments(search_query)

    ambient_lines = []
    seen_ids = set()
    all_anchors = []

    num_segs = len(segments)
    multi_item_mode = num_segs > 1
    max_clara = 2 if multi_item_mode else 4
    max_sprint = 1 if multi_item_mode else 2
    max_icm = 1 if multi_item_mode else 2

    if multi_item_mode:
        ambient_lines.append(f"[Ambient Grounding: Multi-Item Intent Resolution ({num_segs} Segments)]")

    for seg in segments:
        seg_text = seg['text']
        seg_lines = []

        clara_hits = probe_claradb(seg_text, client, model, is_qq=is_qq, limit=max_clara, seen_ids=seen_ids)
        for h in clara_hits:
            m = re.search(r"\[(.*?)\]", h)
            if m:
                all_anchors.append(m.group(1))
            seg_lines.append(f"  - Clara: {h[2:]}" if multi_item_mode else h)

        sprint_hits = probe_sprint_dna(seg_text, client, limit=max_sprint, seen_ids=seen_ids)
        for sh in sprint_hits:
            seg_lines.append(f"  - Sprint: {sh[2:]}" if multi_item_mode else sh)

        icm_hits = probe_icm(seg_text, project=project, is_qq=is_qq, limit=max_icm)
        for ih in icm_hits:
            seg_lines.append(f"  - ICM: {ih[2:]}" if multi_item_mode else ih)

        if seg_lines:
            if multi_item_mode:
                snippet = seg_text[:50] + ("..." if len(seg_text) > 50 else "")
                ambient_lines.append(f"▸ {seg['label']} (\"{snippet}\"):")
                ambient_lines.extend(seg_lines)
            else:
                ambient_lines.append("[ClaraDB Anchors & Matches]")
                ambient_lines.extend(seg_lines)

    duration_ms = round((time.time() - t_start) * 1000, 2)
    breadcrumb = f"> DNA **Grounding**: {' '.join([f'[{a}]' for a in all_anchors[:4]]) if all_anchors else 'Nominal'} ({len(all_anchors)} hits • {duration_ms}ms)"

    if ambient_lines:
        # Prepend explicit breadcrumb anchor to injected message
        ambient_lines.insert(0, f"[Grounding Header: {breadcrumb}]")
        return {
            "injectSteps": [{"ephemeralMessage": "\n".join(ambient_lines)}],
            "meta": {
                "status": "INJECTED",
                "anchors": all_anchors,
                "breadcrumb": breadcrumb,
                "duration_ms": duration_ms
            }
        }

    return {"injectSteps": [], "meta": {"status": "ZERO_MATCHES", "duration_ms": duration_ms}}
