#!/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3
import sys
import json
import os
import re
import subprocess
import socket

def probe_socket(host: str, port: int, timeout: float = 0.15) -> bool:
    """[FEAT-486] 150ms non-blocking TCP socket check."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False

def get_chroma_client():
    """[LAB-021] Resolves local or Tailscale ChromaDB HttpClient with fast-bypass."""
    try:
        import chromadb
    except ImportError:
        return None

    candidates = []
    env_host = os.environ.get("CHROMA_HOST")
    if env_host:
        candidates.append(env_host)
    candidates.extend(["127.0.0.1", "100.122.230.81"])

    port = int(os.environ.get("CHROMA_PORT", 8001))
    for h in candidates:
        if probe_socket(h, port, timeout=0.15):
            try:
                return chromadb.HttpClient(host=h, port=port)
            except Exception:
                continue
    return None

SHALLOW_PROMPTS = {
    "hi", "hello", "hey", "yes", "no", "y", "n", "ok", "okay", "sure", "thanks", "thank you",
    "proceed", "continue", "go ahead", "run it", "do it", "looks good", "status"
}

_fastembed_model = None

def get_fastembed():
    global _fastembed_model
    if _fastembed_model is None:
        try:
            from fastembed import TextEmbedding
            _fastembed_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        except Exception:
            _fastembed_model = False
    return _fastembed_model if _fastembed_model is not False else None

def clean_prompt(text: str) -> str:
    cleaned = re.sub(r"<SYSTEM_MESSAGE>.*?</SYSTEM_MESSAGE>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<.*?>", "", cleaned)
    cleaned = re.sub(r"^\[Message\].*?content=", "", cleaned)
    return cleaned.strip()

# Universal pattern for flexible list segmentation (1), 1., [1], (1), a), bullets)
LIST_PATTERN = re.compile(
    r'(?:^|\n|\s+)'
    r'(?:'
        r'(\d+)[\)\.]|'
        r'\[(\d+)\]|'
        r'\((\d+)\)|'
        r'(?<![a-zA-Z0-9])([a-zA-Z])[\)\.]'
    r')\s+'
)

def extract_prompt_segments(cleaned: str) -> list[dict]:
    """Segment compound prompts (e.g. 1) 2) 3), bullets, or lettered items)."""
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
    """Fail-safe: Extract exact IDs via pure regex without database or network dependency."""
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

def get_recent_memories(limit=4):
    """Retrieve the newest N memories sorted chronologically by creation date."""
    try:
        res = subprocess.run(
            ["icm", "list", "-a", "-s", "created"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode != 0 or not res.stdout.strip():
            return []
            
        blocks = res.stdout.split("--- ")
        recent = []
        for b in blocks:
            if not b.strip():
                continue
            lines = b.strip().split("\n")
            topic = ""
            summary = ""
            created = ""
            for l in lines:
                l_s = l.strip()
                if l_s.startswith("topic:"):
                    topic = l_s.split(":", 1)[1].strip()
                elif l_s.startswith("summary:"):
                    summary = l_s.split(":", 1)[1].strip()
                elif l_s.startswith("created:"):
                    created = l_s.split(":", 1)[1].strip()
            if summary and topic != "preferences" and "[REMOVED]" not in summary:
                recent.append({"topic": topic, "summary": summary, "created": created})
                if len(recent) >= limit:
                    break
        return recent
    except Exception:
        return []

def probe_claradb(text: str, client=None, model=None, is_qq: bool = False, limit: int = 4, seen_ids: set = None, hook_errors: list = None):
    """Extract exact IDs and perform Dynamic Distance Banding against ClaraDB Chroma."""
    results = []
    if seen_ids is None:
        seen_ids = set()

    # 1. Exact Literal ID Lookups (always reliable)
    bkms = re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE)
    feats = re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE)
    labs = re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE)

    try:
        if client is None:
            client = get_chroma_client()
        if not client:
            if hook_errors is not None and not any("ChromaDB unreachable" in e for e in hook_errors):
                hook_errors.append("ChromaDB unreachable on port 8001 (using literal regex fallback)")
            # Fall back to pure literal extraction
            for b in bkms:
                b_up = b.upper()
                if b_up not in seen_ids:
                    seen_ids.add(b_up)
                    results.append(f"- [{b_up}] Protocol Anchor (Offline)")
            for f in feats:
                f_up = f.upper()
                if f_up not in seen_ids:
                    seen_ids.add(f_up)
                    results.append(f"- [{f_up}] Feature Anchor (Offline)")
            return results

        # Exact ID Lookups (< 2ms)
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

        # Dynamic Distance-Banded Reverse Lookup (< 15ms)
        if model is None:
            model = get_fastembed()
        words = set(re.findall(r"\w+", text.lower()))
        significant_words = {w for w in words if len(w) > 2 and w not in SHALLOW_PROMPTS}

        if model and len(significant_words) >= 1 and len(results) < limit:
            emb = list(model.embed([text[:200]]))[0].tolist()

            # Query candidate pool from feature_dna
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

            # Query candidate pool from behavioral_dna
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

            # Query candidate pool from philosophy_dna if prompt targets wisdom/philosophy
            phl_triggers = {"philosophy", "wisdom", "origin", "synthesis", "gem", "pearl", "vector"}
            if (any(t in words for t in phl_triggers) or bool(re.search(r"\b(WIS-\d+|PHL-\d+)\b", text, re.IGNORECASE))) and len(results) < limit:
                try:
                    col_phl = client.get_collection("philosophy_dna")
                    r_phl = col_phl.query(query_embeddings=[emb], n_results=2)
                    phl_dists = r_phl.get("distances", [[]])[0]
                    for i, dist in enumerate(phl_dists):
                        if len(results) >= limit:
                            break
                        meta = r_phl["metadatas"][0][i]
                        wid = meta.get("wisdom_id", "WIS")
                        if wid in seen_ids:
                            continue
                        title = meta.get("title", "Wisdom")
                        if dist <= 0.65:
                            seen_ids.add(wid)
                            results.append(f"- [{wid}] {title}")
                except Exception as phl_e:
                    if hook_errors is not None:
                        hook_errors.append(f"philosophy_dna query failed: {phl_e}")
    except Exception as e:
        if hook_errors is not None:
            hook_errors.append(f"ClaraDB probe exception: {e}")
        # Fallback to literal IDs on unexpected database error
        for l_id in extract_literal_ids(text):
            m = re.search(r"\[(.*?)\]", l_id)
            tid = m.group(1) if m else l_id
            if tid not in seen_ids:
                seen_ids.add(tid)
                results.append(l_id)

    return results

# [FEAT-557] Targeted sprint_dna ambient gate
_SPRINT_KEYWORD_RE = re.compile(
    r"\b(?:SPR(?:INT)?[-_ ]?\d+|Story\s+\d+\.\d+|sprint_dna)\b|\bsprint\b|\bplan\b|\bretro\b",
    re.IGNORECASE,
)

def is_sprint_query(text: str) -> bool:
    if not text:
        return False
    return bool(_SPRINT_KEYWORD_RE.search(text))

def probe_sprint_dna(text: str, client=None, limit: int = 2, seen_ids: set = None, hook_errors: list = None):
    """Query sprint_dna collection with fail-open safety."""
    if not is_sprint_query(text):
        return []
    if seen_ids is None:
        seen_ids = set()

    try:
        if client is None:
            client = get_chroma_client()
        if not client:
            return []
        col = client.get_collection("sprint_dna")
        res = col.query(query_texts=[text[:500]], n_results=limit)
    except Exception as e:
        if hook_errors is not None:
            hook_errors.append(f"sprint_dna query failed: {e}")
        return []

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
            )
            snippet = snippet[:60]
        line = f"- [sprint_dna:{sprint_id}] L{level} {kind} (w={weight:.2f})"
        if snippet:
            line += f" — {snippet}"
        seen_ids.add(sprint_id)
        results.append(line)
        if len(results) >= limit:
            break
    return results

def probe_icm(text: str, project: str, is_qq: bool = False, limit: int = 2, hook_errors: list = None):
    """Recall from ICM with error catching."""
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
        elif res.returncode != 0 and hook_errors is not None:
            hook_errors.append(f"icm recall returned code {res.returncode}")
    except Exception as e:
        if hook_errors is not None:
            hook_errors.append(f"icm recall failed: {e}")
    return []

def main():
    hook_errors = []
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        sys.stderr.write(f"\n\033[31m⚠️ [Hook Error / Degraded Mode]\033[0m Invalid hook payload on stdin: {e} (hook needs fix)\n")
        print(json.dumps({"injectSteps": []}))
        return

    # [Action 1: Junior / Air Context & Swarm Delegation Bypass]
    # Sisyphus-Junior, Atlas cascade workers, and programmatic delegation dispatches
    # MUST NOT receive ambient wake-up packs, recent memories, or ClaraDB/ICM injections.
    agent_name = (payload.get("agent") or payload.get("agentName") or "").lower()
    session_title = (payload.get("sessionTitle") or payload.get("title") or "").lower()
    user_input_raw = (payload.get("userMessage") or payload.get("prompt") or payload.get("last_user_message") or "")
    if ("junior" in agent_name or "junior" in session_title or "air" in agent_name or
            any(marker in user_input_raw for marker in ["[STORY DELEGATION TARGET", "[TASK:", "[ORCHESTRATION INSTRUCTIONS", "[SPOON-FED TASK", "[MOMUS:", "[LIBRARIAN:"])):
        print(json.dumps({"injectSteps": []}))
        return

    inv_num = payload.get("invocationNum", 1)
    workspace_paths = payload.get("workspacePaths", [])
    project = os.path.basename(workspace_paths[0]) if workspace_paths else "Dev_Lab"

    # 1. Session Start: Generous Wake-Up Pack + Chronological Recency Flush
    if inv_num == 1:
        session_start_lines = []
        try:
            res = subprocess.run(
                ["icm", "wake-up", "-t", "200", "-p", project],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                clean_lines = [l for l in res.stdout.strip().split("\n") if "[REMOVED]" not in l]
                session_start_lines.append("\n".join(clean_lines))
            elif res.returncode != 0:
                hook_errors.append(f"icm wake-up returned code {res.returncode}")
        except Exception as e:
            hook_errors.append(f"icm wake-up error: {e}")

        # Recency Flush: Top 4 recent memories
        recent_mems = get_recent_memories(limit=4)
        if recent_mems:
            session_start_lines.append("\n## Recently Learned & Latest Sprint Decisions (Last Session)")
            for m in recent_mems:
                session_start_lines.append(f"- [{m['created']}] ({m['topic']}) {m['summary']}")

        if hook_errors:
            err_msg = "; ".join(hook_errors[:3])
            sys.stderr.write(f"\n\033[31m⚠️ [Hook Error / Degraded Mode]\033[0m Session wake-up degraded: {err_msg} (hook needs fix)\n")
            session_start_lines.insert(0, f"[⚠️ AMBIENT HOOK WARNING: Session wake-up degraded — {err_msg} — hook needs to be fixed!]")

        if session_start_lines:
            print(json.dumps({
                "injectSteps": [{
                    "ephemeralMessage": "\n".join(session_start_lines)
                }]
            }))
            return
        print(json.dumps({"injectSteps": []}))
        return

    # 2. Subsequent Turns: Extract User Query
    transcript_path = payload.get("transcriptPath")
    if not transcript_path or not os.path.exists(transcript_path):
        print(json.dumps({"injectSteps": []}))
        return

    last_user_prompt = None
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if record.get("type") == "USER_INPUT":
                        last_user_prompt = record.get("content", "")
                except Exception:
                    pass
    except Exception as e:
        hook_errors.append(f"Transcript read failed: {e}")

    if not last_user_prompt:
        if hook_errors:
            err_msg = "; ".join(hook_errors[:3])
            sys.stderr.write(f"\n\033[31m⚠️ [Hook Error / Degraded Mode]\033[0m {err_msg} (hook needs fix)\n")
        print(json.dumps({"injectSteps": []}))
        return

    cleaned = clean_prompt(last_user_prompt)
    if not cleaned:
        print(json.dumps({"injectSteps": []}))
        return

    ambient_lines = []
    seen_ids = set()
    all_summary_clara = []
    all_summary_icm = []

    # Detect QQ Mode (High-Altitude Inquiry)
    is_qq = bool(re.match(r"^qq\b", cleaned, re.IGNORECASE))
    search_query = re.sub(r"^qq[:\s]*", "", cleaned, flags=re.IGNORECASE).strip()

    # Pre-warm shared client and embed model once
    chroma_client = None
    fastembed_model = None
    try:
        chroma_client = get_chroma_client()
        fastembed_model = get_fastembed()
    except Exception as client_e:
        hook_errors.append(f"Client init error: {client_e}")

    # Extract segments (supports 1), 2), bullets, lettered, or single query)
    segments = []
    try:
        segments = extract_prompt_segments(search_query)
    except Exception as seg_e:
        hook_errors.append(f"Segmentation regex failed: {seg_e}")
        segments = [{'id': '1', 'label': 'Query', 'text': search_query}]

    num_segs = len(segments)
    multi_item_mode = num_segs > 1

    # Dynamic budget scaling per segment
    if num_segs <= 1:
        max_clara_per_seg = 6
        max_sprint_per_seg = 3
        max_icm_per_seg = 3
    elif num_segs <= 3:
        max_clara_per_seg = 2
        max_sprint_per_seg = 1
        max_icm_per_seg = 2
    else:
        max_clara_per_seg = 2
        max_sprint_per_seg = 1
        max_icm_per_seg = 1

    if multi_item_mode:
        ambient_lines.append(f"[Ambient Grounding: Multi-Item Intent Resolution ({num_segs} Segments)]")

    for seg in segments:
        seg_text = seg['text']
        seg_lines = []

        # 1. ClaraDB probe for segment
        try:
            clara_hits = probe_claradb(
                seg_text, client=chroma_client, model=fastembed_model,
                is_qq=is_qq, limit=max_clara_per_seg, seen_ids=seen_ids, hook_errors=hook_errors
            )
            for h in clara_hits:
                match = re.search(r"\[(.*?)\]", h)
                if match:
                    all_summary_clara.append(match.group(1))
                if multi_item_mode:
                    seg_lines.append(f"  - Clara: {h[2:]}")
                else:
                    seg_lines.append(h)
        except Exception as ce:
            hook_errors.append(f"Clara segment probe failed ({seg['label']}): {ce}")
            # Salvage exact literal anchors
            for lit in extract_literal_ids(seg_text):
                seg_lines.append(f"  - Fallback Anchor: {lit[2:]}")

        # 2. Sprint DNA probe for segment
        try:
            sprint_hits = probe_sprint_dna(
                seg_text, client=chroma_client, limit=max_sprint_per_seg,
                seen_ids=seen_ids, hook_errors=hook_errors
            )
            for sh in sprint_hits:
                if multi_item_mode:
                    seg_lines.append(f"  - Sprint: {sh[2:]}")
                else:
                    seg_lines.append(sh)
        except Exception as se:
            hook_errors.append(f"Sprint segment probe failed ({seg['label']}): {se}")

        # 3. ICM probe for segment
        try:
            icm_hits = probe_icm(
                seg_text, project=project, is_qq=is_qq,
                limit=max_icm_per_seg, hook_errors=hook_errors
            )
            for ih in icm_hits:
                m_top = re.search(r"\((.*?)\)", ih)
                if m_top:
                    all_summary_icm.append(m_top.group(1))
                if multi_item_mode:
                    seg_lines.append(f"  - ICM: {ih[2:]}")
                else:
                    seg_lines.append(ih)
        except Exception as ie:
            hook_errors.append(f"ICM segment probe failed ({seg['label']}): {ie}")

        if seg_lines:
            if multi_item_mode:
                snippet = seg_text[:50] + ("..." if len(seg_text) > 50 else "")
                ambient_lines.append(f"▸ {seg['label']} (\"{snippet}\"):")
                ambient_lines.extend(seg_lines)
            else:
                ambient_lines.append("[ClaraDB Anchors & Matches]")
                ambient_lines.extend(seg_lines)

    # 4. Global Fallback if no lines generated
    if not ambient_lines:
        literal_fallbacks = extract_literal_ids(search_query)
        if literal_fallbacks:
            ambient_lines.append("[Direct Literal Code/Protocol Anchors]")
            ambient_lines.extend(literal_fallbacks)

    # 5. Fail-Graceful Warning & Error Reporting
    if hook_errors:
        err_summary = "; ".join(hook_errors[:3])
        # Prominent stderr alert for the operator
        try:
            sys.stderr.write(f"\n\033[31m⚠️ [Hook Error / Degraded Mode]\033[0m {err_summary} (hook needs fix, partial context preserved)\n")
            sys.stderr.flush()
        except Exception:
            pass

        # Injected prompt notice so agent and transcript record the defect
        warning_header = f"[⚠️ AMBIENT HOOK WARNING: Degraded Execution — Hook error(s) occurred and need to be fixed: {err_summary}]"
        ambient_lines.insert(0, warning_header)

    # 6. Emit Final JSON Output
    if ambient_lines:
        summary_parts = []
        if all_summary_clara:
            summary_parts.append("Clara: " + ", ".join(all_summary_clara[:3]))
        if all_summary_icm:
            summary_parts.append("ICM: " + ", ".join(all_summary_icm[:2]))
        if multi_item_mode:
            summary_parts.insert(0, f"{num_segs} items")

        detail = " | ".join(summary_parts) if summary_parts else "Context Active"
        try:
            status_color = "\033[33m" if hook_errors else "\033[36m"
            sys.stderr.write(f"\n{status_color}🧬 [Ambient Memory & Knowledge]\033[0m {detail}\n")
            sys.stderr.flush()
        except Exception:
            pass

        print(json.dumps({
            "injectSteps": [{
                "ephemeralMessage": "\n".join(ambient_lines)
            }]
        }))
    else:
        print(json.dumps({"injectSteps": []}))

if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_e:
        # Ultimate fallback: NEVER crash the hook runner with exit status 1
        err_text = f"Fatal unhandled exception in icm_hook: {fatal_e}"
        try:
            sys.stderr.write(f"\n\033[31m⚠️ [Hook Fatal Crash]\033[0m {err_text} (hook needs to be fixed!)\n")
            sys.stderr.flush()
        except Exception:
            pass
        print(json.dumps({
            "injectSteps": [{
                "ephemeralMessage": f"[⚠️ AMBIENT HOOK WARNING: Fatal hook error occurred and needs to be fixed: {err_text}]"
            }]
        }))
