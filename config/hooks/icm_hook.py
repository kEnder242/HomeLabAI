#!/usr/bin/env python3
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

def probe_claradb(text: str, is_qq: bool = False):
    """Extract exact IDs and perform Dynamic Distance Banding against ClaraDB Chroma."""
    results = []
    bkms = re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE)
    feats = re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE)
    labs = re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE)

    try:
        import chromadb
        client = get_chroma_client()
        if not client:
            return results
        
        # 1. Exact ID Lookups (< 2ms)
        if bkms:
            col_bkm = client.get_collection("behavioral_dna")
            for b in bkms:
                r = col_bkm.get(where={"bkm_id": b.upper()})
                if r and r.get("metadatas"):
                    meta = r["metadatas"][0]
                    results.append(f"- [{b.upper()}] {meta.get('name', 'Protocol')}")

        if feats:
            col_feat = client.get_collection("feature_dna")
            for f in feats:
                r = col_feat.get(where={"feature_id": f.upper()})
                if r and r.get("metadatas"):
                    meta = r["metadatas"][0]
                    status = meta.get("status", "ACTIVE")
                    results.append(f"- [{f.upper()}] {meta.get('name', 'Feature')} ({status})")

        if labs:
            col_bkm = client.get_collection("behavioral_dna")
            all_infra = col_bkm.get(where={"type": "INFRA"})
            if all_infra and all_infra.get("metadatas"):
                for l in labs:
                    l_target = l.upper()
                    for meta in all_infra["metadatas"]:
                        name = meta.get("name", "")
                        if l_target in name.upper():
                            results.append(f"- [{l_target}] {name}")
                            break

        # 2. Dynamic Distance-Banded Reverse Lookup (< 15ms)
        model = get_fastembed()
        words = set(re.findall(r"\w+", text.lower()))
        significant_words = {w for w in words if len(w) > 2 and w not in SHALLOW_PROMPTS}
        
        if model and len(significant_words) >= 1:
            emb = list(model.embed([text[:200]]))[0].tolist()
            
            # Query candidate pool of 6 from feature_dna
            col_feat = client.get_collection("feature_dna")
            r_feat = col_feat.query(query_embeddings=[emb], n_results=6)
            
            feat_dists = r_feat.get("distances", [[]])[0]
            if feat_dists:
                min_feat_dist = min(feat_dists)
                for i, dist in enumerate(feat_dists):
                    meta = r_feat["metadatas"][0][i]
                    name = meta.get("name", "Feature")
                    fid = meta.get("feature_id") or r_feat["ids"][0][i].split("_")[0]
                    status = meta.get("status", "ACTIVE")
                    
                    has_kw = any(w in name.lower() for w in significant_words)
                    
                    is_in_band = (dist <= 0.55) or (dist <= min_feat_dist + 0.10 and dist < 0.62) or (has_kw and dist <= 0.60)
                    if is_qq:
                        is_in_band = is_in_band or (dist <= 0.60)
                        
                    if is_in_band:
                        res_str = f"- [{fid}] {name} ({status})"
                        if res_str not in results:
                            results.append(res_str)

            # Query candidate pool of 4 from behavioral_dna
            col_bkm = client.get_collection("behavioral_dna")
            r_bkm = col_bkm.query(query_embeddings=[emb], n_results=4)
            bkm_dists = r_bkm.get("distances", [[]])[0]
            if bkm_dists:
                min_bkm_dist = min(bkm_dists)
                for i, dist in enumerate(bkm_dists):
                    meta = r_bkm["metadatas"][0][i]
                    name = meta.get("name", "Protocol")
                    bkm_id = meta.get("bkm_id")
                    
                    has_kw = any(w in name.lower() for w in significant_words)
                    is_in_band = (dist <= 0.55) or (dist <= min_bkm_dist + 0.10 and dist < 0.62) or (has_kw and dist <= 0.60)
                    if is_qq:
                        is_in_band = is_in_band or (dist <= 0.60)
                        
            # Query sprint_dna if prompt targets sprints or stories
            sprint_triggers = {"sprint", "story", "retro", "plan", "archive"}
            sprint_kw = any(t in words for t in sprint_triggers) or bool(re.search(r"\b(SPR-\d+|Story\s*\d+)\b", text, re.IGNORECASE))
            if sprint_kw:
                try:
                    col_spr = client.get_collection("sprint_dna")
                    r_spr = col_spr.query(query_embeddings=[emb], n_results=3)
                    spr_dists = r_spr.get("distances", [[]])[0]
                    for i, dist in enumerate(spr_dists):
                        meta = r_spr["metadatas"][0][i]
                        sid = meta.get("sprint_id", "SPR")
                        st_id = meta.get("story_id")
                        level = meta.get("level", "CHUNK")
                        w = meta.get("recency_weight", 1.0)
                        if dist <= 0.65:
                            label = f"- [{sid}:{st_id}] ({level}, w={w:.2f})" if st_id else f"- [{sid}] ({level}, w={w:.2f})"
                            if label not in results:
                                results.append(label)
                except Exception:
                    pass

            # Query philosophy_dna if prompt targets wisdom or philosophy
            phl_triggers = {"philosophy", "wisdom", "origin", "synthesis", "gem", "pearl", "vector"}
            if any(t in words for t in phl_triggers) or bool(re.search(r"\b(WIS-\d+|PHL-\d+)\b", text, re.IGNORECASE)):
                try:
                    col_phl = client.get_collection("philosophy_dna")
                    r_phl = col_phl.query(query_embeddings=[emb], n_results=2)
                    phl_dists = r_phl.get("distances", [[]])[0]
                    for i, dist in enumerate(phl_dists):
                        meta = r_phl["metadatas"][0][i]
                        wid = meta.get("wisdom_id", "WIS")
                        title = meta.get("title", "Wisdom")
                        if dist <= 0.65:
                            res_str = f"- [{wid}] {title}"
                            if res_str not in results:
                                results.append(res_str)
                except Exception:
                    pass
    except Exception:
        pass

    return results

# [FEAT-557] Targeted sprint_dna ambient gate ---------------------------------
_SPRINT_KEYWORD_RE = re.compile(
    r"\b(?:SPR(?:INT)?[-_ ]?\d+|Story\s+\d+\.\d+|sprint_dna)\b|\bsprint\b|\bplan\b|\bretro\b",
    re.IGNORECASE,
)


def is_sprint_query(text: str) -> bool:
    """True when the prompt carries sprint-planning keyword anchors.

    Gates ``sprint_dna`` retrieval to prompts that are actually about sprint
    history / story evolution / planning/retrospection, keeping the hook
    targeted (per Story 76.3) rather than firing on every turn.
    """
    if not text:
        return False
    return bool(_SPRINT_KEYWORD_RE.search(text))


def probe_sprint_dna(text: str, limit: int = 4, timeout: float = 0.150):
    """Query the ``sprint_dna`` collection when sprint keywords are present.

    150ms fail-open: any connection / query issue returns an empty list so the
    ambient hook never blocks or stalls the main prompt pipeline.

    Returns a list of human-readable lines like
    ``- [SPR_74_0] Overview (recency 0.85)``.
    """
    if not is_sprint_query(text):
        return []
    try:
        # NOTE: `get_chroma_client()` imports chromadb internally; we never
        # reference the module name here, so no local import is required.
        client = get_chroma_client()
        if not client:
            return []
        col = client.get_collection("sprint_dna")
        res = col.query(query_texts=[text[:500]], n_results=limit)
    except Exception:
        return []

    results = []
    metas = (res.get("metadatas") or [[]])[0] or []
    docs = (res.get("documents") or [[]])[0] or []
    ids = (res.get("ids") or [[]])[0] or []
    for i, meta in enumerate(metas):
        sprint_id = meta.get("sprint_id", ids[i][:14] if i < len(ids) else "SPR")
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
            snippet = snippet[:80]
        line = f"- [sprint_dna:{sprint_id}] L{level} {kind} (recency {weight})"
        if snippet:
            line += f" — {snippet}"
        if line not in results:
            results.append(line)
        if len(results) >= limit:
            break
    return results


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
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
        except Exception:
            pass

        # Recency Flush: Top 4 recent memories (yesterday / last session / recent sprint)
        recent_mems = get_recent_memories(limit=4)
        if recent_mems:
            session_start_lines.append("\n## Recently Learned & Latest Sprint Decisions (Last Session)")
            for m in recent_mems:
                session_start_lines.append(f"- [{m['created']}] ({m['topic']}) {m['summary']}")

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
    except Exception:
        pass

    if not last_user_prompt:
        print(json.dumps({"injectSteps": []}))
        return

    cleaned = clean_prompt(last_user_prompt)
    words = cleaned.lower().split()

    ambient_lines = []

    # Detect QQ Mode (High-Altitude Inquiry)
    is_qq = bool(re.match(r"^qq\b", cleaned, re.IGNORECASE))
    search_query = re.sub(r"^qq[:\s]*", "", cleaned, flags=re.IGNORECASE).strip()
    search_words = search_query.lower().split()

    # Step A: ClaraDB Probe (Exact IDs + Dynamic Distance Banding)
    clara_hits = probe_claradb(search_query, is_qq=is_qq)
    if clara_hits:
        ambient_lines.append("[ClaraDB Anchors & Matches]")
        ambient_lines.extend(clara_hits[:6])

    # Step A.1: [FEAT-557] Targeted sprint_dna hook (fails open in <=150ms)
    if is_sprint_query(search_query):
        sprint_hits = probe_sprint_dna(search_query)
        if sprint_hits:
            if not ambient_lines:
                ambient_lines.append("[Sprint DNA Anchors]")
            else:
                ambient_lines.append("\n[Sprint DNA Anchors]")
            ambient_lines.extend(sprint_hits)

    # Step B: ICM Recall
    if len(search_words) >= 2 and search_query.lower() not in SHALLOW_PROMPTS:
        limit = "3" if is_qq else "2"
        score_threshold = 0.40 if is_qq else 0.45

        try:
            res = subprocess.run(
                ["icm", "recall", search_query[:200], "-f", "json", "-l", limit, "-p", project],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                memories = json.loads(res.stdout)
                strong = [m for m in memories if m.get("score", 0) >= score_threshold]
                if strong:
                    header = "[ICM Research Grounding (QQ Boost)]" if is_qq else "[ICM Ambient Memory]"
                    if not ambient_lines:
                        ambient_lines.append(header)
                    else:
                        ambient_lines.append(f"\n{header}")
                    for m in strong:
                        ambient_lines.append(f"- ({m.get('topic')}) {m.get('summary')}")
        except Exception:
            pass

    if ambient_lines:
        summary_parts = []
        if clara_hits:
            ids = []
            for h in clara_hits:
                match = re.search(r"\[(.*?)\]", h)
                if match:
                    ids.append(match.group(1))
            if ids:
                summary_parts.append("Clara: " + ", ".join(ids[:3]))
        if 'strong' in locals() and strong:
            topics = list({m.get('topic') for m in strong if m.get('topic')})
            if topics:
                summary_parts.append("ICM: " + ", ".join(topics[:2]))

        detail = " | ".join(summary_parts) if summary_parts else "Context Active"
        try:
            sys.stderr.write(f"\n\033[36m🧬 [Ambient Memory & Knowledge]\033[0m {detail}\n")
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
    main()
