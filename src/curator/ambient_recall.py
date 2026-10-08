#!/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3
"""[FEAT-600 / FEAT-631 / LAB-019 / LAB-112 / BKM-060] Canonical Ambient Recall Engine.

Executes turn-gated, dynamic distance-banded semantic recall against ChromaDB :8001
collections (behavioral_dna, feature_dna, wisdom_dna, inspiration_dna, rdna, loop_dna, sprint_dna)
and in-process SQLite memories. Injects full DNA document bodies and memory summaries.
"""

import json
import logging
import os
import re
import socket
import sys
import time
import urllib.request

logger = logging.getLogger("ambient_recall")

CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8001"))

SHALLOW_PROMPTS = {
    "hi", "hello", "hey", "yes", "no", "y", "n", "ok", "okay", "sure", "thanks", "thank you",
    "proceed", "continue", "go ahead", "run it", "do it", "looks good", "status", "qq", "qq!"
}
SHALLOWER_WORDS = {"and", "the", "for", "with", "this", "that", "from", "into", "onto", "your", "have"}

LIST_PATTERN = re.compile(
    r"(?:^|\n|\s+)"
    r"(?:"
    r"(\d+)[\)\.]|"
    r"\[(\d+)\]|"
    r"\((\d+)\)|"
    r"(?<![a-zA-Z0-9])([a-zA-Z])[\)\.]"
    r")\s+"
)

_SPRINT_KEYWORD_RE = re.compile(
    r"\b(?:SPR(?:INT)?[-_ ]?\d+|Story\s+\d+\.\d+|sprint_dna)\b|\bsprint\b|\bplan\b|\bretro\b",
    re.IGNORECASE,
)

BKM_FASTPATH_TRIGGERS = [
    (
        re.compile(r"\b(?:save\s+to\s+git|add\s+to\s+git|upload\s+to\s+git|checkpoint|save\s+state|commit\s+locally)\b", re.IGNORECASE),
        "BKM-009",
        "Local Git Checkpoint & Session Continuity Protocol",
    ),
    (
        re.compile(r"\b(?:git\s+push|push\s+origin|never\s+push|git\s+discipline|git\s+boundary)\b", re.IGNORECASE),
        "BKM-040",
        "Virtual Environment Hygiene & Git Curation",
    ),
    (
        re.compile(r"\b(?:dual\s+push|git\s+mirror|secondary\s+mirror|cloud\s+redundancy)\b", re.IGNORECASE),
        "BKM-053",
        "Multi-Remote Secondary Git Mirror & Cloud Redundancy Protocol",
    ),
    (
        re.compile(r"\b(?:tri-loop|delegation\s+owner|story\s+owner|owner\s+tag)\b", re.IGNORECASE),
        "BKM-049",
        "Tri-Loop Story Delegation & Owner Tag Mandate",
    ),
]

_fastembed_model = None


def get_fastembed():
    global _fastembed_model
    if _fastembed_model is None:
        try:
            from fastembed import TextEmbedding

            _fastembed_model = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        except Exception:
            _fastembed_model = False
    return _fastembed_model if _fastembed_model is not False else None


def probe_socket(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


class ChromaRestClient:
    """[LAB-019 / LAB-021] Lightweight REST client for ChromaDB port 8001 bypassing chromadb/torch import."""
    def __init__(self, base_url="http://127.0.0.1:8001/api/v2/tenants/default_tenant/databases/default_database"):
        self.base_url = base_url.rstrip("/")
        self._col_cache = {}
        self._refresh_cols()

    def _refresh_cols(self):
        try:
            req = urllib.request.Request(f"{self.base_url}/collections")
            with urllib.request.urlopen(req, timeout=0.4) as resp:
                cols = json.loads(resp.read().decode("utf-8"))
                self._col_cache = {c["name"]: c["id"] for c in cols}
        except Exception:
            pass

    def get_collection(self, name):
        col_id = self._col_cache.get(name)
        if not col_id:
            self._refresh_cols()
            col_id = self._col_cache.get(name)
        if not col_id:
            raise KeyError(f"Collection {name} not found")
        return ChromaRestCollection(self.base_url, name, col_id)

    def heartbeat(self):
        try:
            req = urllib.request.Request("http://127.0.0.1:8001/api/v1/heartbeat")
            with urllib.request.urlopen(req, timeout=0.25) as resp:
                return resp.status == 200
        except Exception:
            return True


class ChromaRestCollection:
    def __init__(self, base_url, name, col_id):
        self.base_url = base_url
        self.name = name
        self.col_id = col_id

    def get(self, where=None, ids=None, limit=None):
        payload = {}
        if where:
            payload["where"] = where
        if ids:
            payload["ids"] = ids
        if limit:
            payload["limit"] = limit
        url = f"{self.base_url}/collections/{self.col_id}/get"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def query(
        self,
        query_embeddings=None,
        query_texts=None,
        n_results=5,
        where=None,
    ):
        if query_embeddings is None and query_texts is not None:
            model = get_fastembed()
            if model is not None:
                query_embeddings = [list(e) for e in model.embed(query_texts)]
        payload = {"n_results": n_results}
        if query_embeddings:
            payload["query_embeddings"] = query_embeddings
        if where:
            payload["where"] = where
        url = f"{self.base_url}/collections/{self.col_id}/query"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return json.loads(resp.read().decode("utf-8"))


def get_chroma_client():
    try:
        candidates = []
        env_host = os.environ.get("CHROMA_HOST")
        if env_host:
            candidates.append(env_host)
        candidates.extend(["127.0.0.1", "100.122.230.81"])

        port = int(os.environ.get("CHROMA_PORT", 8001))
        for h in candidates:
            if probe_socket(h, port, timeout=0.25):
                return ChromaRestClient(base_url=f"http://{h}:{port}/api/v2/tenants/default_tenant/databases/default_database")
    except Exception:
        pass
    return None


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
        bullet_matches = list(re.finditer(r"(?:^|\n)\s*[-*]\s+", cleaned))
        if len(bullet_matches) >= 2:
            segments = []
            for i, bm in enumerate(bullet_matches):
                start = bm.end()
                end = (
                    bullet_matches[i + 1].start()
                    if i + 1 < len(bullet_matches)
                    else len(cleaned)
                )
                seg_text = cleaned[start:end].strip()
                if seg_text:
                    segments.append(
                        {
                            "id": f"bullet_{i+1}",
                            "label": f"Bullet {i+1}",
                            "text": seg_text,
                        }
                    )
            return segments
        return [{"id": "1", "label": "Query", "text": cleaned}]

    segments = []
    preamble = cleaned[: matches[0].start()].strip()
    if preamble and len(preamble.split()) >= 3:
        segments.append({"id": "0", "label": "Context", "text": preamble})

    for i, m in enumerate(matches):
        marker_id = m.group(1) or m.group(2) or m.group(3) or m.group(4) or str(i + 1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        seg_text = cleaned[start:end].strip()
        if seg_text:
            segments.append(
                {"id": marker_id, "label": f"Item {marker_id}", "text": seg_text}
            )

    return segments if segments else [{"id": "1", "label": "Query", "text": cleaned}]


def extract_literal_ids(text: str) -> list[str]:
    results = []
    bkms = re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE)
    feats = re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE)
    labs = re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE)
    wis = re.findall(r"\b(WIS-\d{3}|PHL-\d{3}|INS-\d{3})\b", text, re.IGNORECASE)
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

    for pattern, bkm_id, name in BKM_FASTPATH_TRIGGERS:
        if pattern.search(text) and f"- [{bkm_id}]" not in "".join(results):
            results.append(f"- [{bkm_id}] {name} (Trigger Match)")

    return results


def get_recent_memories(limit=4):
    """[LAB-019 / BKM-082] Retrieve newest relevant memories, filtering out stale commit diffs and transient noise."""
    db_path = os.path.expanduser("~/.local/share/icm/memories.db")
    if not os.path.exists(db_path):
        return []
    try:
        import sqlite3
        import subprocess

        # Resolve current git HEAD of HomeLabAI
        current_head = ""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--short=7", "HEAD"],
                capture_output=True,
                text=True,
                cwd="/home/jallred/Dev_Lab/HomeLabAI",
                timeout=0.5,
            )
            if res.returncode == 0:
                current_head = res.stdout.strip().lower()
        except Exception:
            pass

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.1)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT topic, summary, created_at 
            FROM memories 
            WHERE topic != 'preferences' AND summary NOT LIKE '%[REMOVED]%' AND summary NOT LIKE '%[SUPERSEDED]%'
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (limit * 4,),
        )
        rows = cursor.fetchall()
        conn.close()

        clean_memories = []
        for r in rows:
            if not r or not r[1]:
                continue
            topic, summary, created = r[0], r[1].strip(), r[2]

            # Skip raw AST line scrapes or traceback noise
            if re.match(r"^\d+:\s+", summary) or summary.startswith("HomeLabAI/src/") or summary.startswith("FAILED "):
                continue

            # Filter out stale commit diffs from past sessions
            if any(term in summary.lower() for term in ["stale bytecode", "head mismatch", "different head", "daemon serves"]):
                commit_matches = re.findall(r"\b[0-9a-f]{7,8}\b", summary.lower())
                if commit_matches and current_head and (current_head[:7] not in commit_matches):
                    continue

            clean_memories.append({"topic": topic, "summary": summary, "created": created})
            if len(clean_memories) >= limit:
                break

        return clean_memories
    except Exception:
        return []


def is_turn_start(transcript_path: str) -> tuple[bool, str]:
    """[FEAT-600] Inspects transcript history to verify this is the start of a user turn."""
    if not transcript_path or not os.path.exists(transcript_path):
        return False, ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]

        last_user_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].get("type") == "USER_INPUT":
                last_user_idx = i
                break

        if last_user_idx == -1:
            return False, ""

        last_user_prompt = lines[last_user_idx].get("content", "")
        events_after = lines[last_user_idx + 1:]

        already_injected = any(
            e.get("type") == "EPHEMERAL_MESSAGE"
            and (
                "Grounding Header:" in str(e.get("content", ""))
                or "Ambient Memory" in str(e.get("content", ""))
                or "ClaraDB Anchors" in str(e.get("content", ""))
                or "Ambient Grounding" in str(e.get("content", ""))
            )
            for e in events_after
        )
        if already_injected:
            return False, last_user_prompt

        has_tool_executions = any(
            e.get("type") in ("GENERIC", "TOOL_RESULT") for e in events_after
        )
        if has_tool_executions:
            return False, last_user_prompt

        return True, last_user_prompt
    except Exception:
        return False, ""


def probe_claradb(
    text: str,
    client=None,
    model=None,
    is_qq: bool = False,
    limit: int = 10,
    seen_ids: set = None,
    hook_errors: list = None,
):
    """[BKM-060 / FEAT-631] Probes dedicated DNA buckets with full document body injection."""
    results = []
    if seen_ids is None:
        seen_ids = set()

    bkms = list(re.findall(r"\b(BKM-\d{3})\b", text, re.IGNORECASE))
    feats = list(re.findall(r"\b(FEAT-\d{3,4})\b", text, re.IGNORECASE))
    labs = list(re.findall(r"\b(LAB-\d{3})\b", text, re.IGNORECASE))
    ins_ids = list(re.findall(r"\b(INS-\d{3}|PHL-\d{3})\b", text, re.IGNORECASE))
    wis_ids = list(re.findall(r"\b(WIS-\d{3})\b", text, re.IGNORECASE))
    rdna_ids = list(re.findall(r"\b(RDNA-\d{3})\b", text, re.IGNORECASE))
    loop_ids = list(re.findall(r"\b(LOOP-\d{3}|VIBE-\d{3})\b", text, re.IGNORECASE))

    for pattern, bkm_id, _ in BKM_FASTPATH_TRIGGERS:
        if pattern.search(text) and bkm_id not in bkms:
            bkms.append(bkm_id)

    try:
        if client is None:
            client = get_chroma_client()
        if not client:
            return extract_literal_ids(text)

        # 1. Exact Literal ID Lookups with Full Document Text
        if bkms:
            try:
                col_bkm = client.get_collection("behavioral_dna")
                for b in bkms:
                    b_up = b.upper()
                    if b_up in seen_ids:
                        continue
                    r = col_bkm.get(where={"bkm_id": b_up})
                    if r and r.get("metadatas"):
                        seen_ids.add(b_up)
                        meta = r["metadatas"][0]
                        name = meta.get("name", "Protocol")
                        docs = r.get("documents", [])
                        doc_text = docs[0].strip() if docs and docs[0] else ""
                        if doc_text:
                            results.append(f"### [{b_up}] {name}\n{doc_text}\n")
                        else:
                            results.append(f"- [{b_up}] {name}")
            except Exception:
                pass

        if feats:
            try:
                col_feat = client.get_collection("feature_dna")
                for f in feats:
                    f_up = f.upper()
                    if f_up in seen_ids:
                        continue
                    r = col_feat.get(where={"feature_id": f_up})
                    if r and r.get("metadatas"):
                        seen_ids.add(f_up)
                        meta = r["metadatas"][0]
                        name = meta.get("name", "Feature")
                        status = meta.get("status", "ACTIVE")
                        docs = r.get("documents", [])
                        doc_text = docs[0].strip() if docs and docs[0] else ""
                        if doc_text:
                            results.append(f"### [{f_up}] {name} ({status})\n{doc_text}\n")
                        else:
                            results.append(f"- [{f_up}] {name} ({status})")
            except Exception:
                pass

        if ins_ids:
            try:
                col_ins = None
                try:
                    col_ins = client.get_collection("inspiration_dna")
                except Exception:
                    col_ins = client.get_collection("philosophy_dna")
                if col_ins:
                    for i_id in ins_ids:
                        i_up = i_id.upper()
                        if i_up in seen_ids:
                            continue
                        r = col_ins.get(ids=[i_up])
                        if not (r and r.get("metadatas")):
                            r = col_ins.get(where={"inspiration_id": i_up})
                        if r and r.get("metadatas"):
                            seen_ids.add(i_up)
                            meta = r["metadatas"][0]
                            title = meta.get("title", meta.get("name", "Inspiration"))
                            docs = r.get("documents", [])
                            doc_text = docs[0].strip() if docs and docs[0] else ""
                            if doc_text:
                                results.append(f"### [{i_up}] {title}\n{doc_text}\n")
                            else:
                                results.append(f"- [{i_up}] {title}")
            except Exception:
                pass

        if wis_ids:
            try:
                col_wis = client.get_collection("wisdom_dna")
                for w in wis_ids:
                    w_up = w.upper()
                    if w_up in seen_ids:
                        continue
                    r = col_wis.get(ids=[w_up])
                    if not (r and r.get("metadatas")):
                        r = col_wis.get(where={"wisdom_id": w_up})
                    if r and r.get("metadatas"):
                        seen_ids.add(w_up)
                        meta = r["metadatas"][0]
                        title = meta.get("title", meta.get("name", "Wisdom"))
                        docs = r.get("documents", [])
                        doc_text = docs[0].strip() if docs and docs[0] else ""
                        if doc_text:
                            results.append(f"### [{w_up}] {title}\n{doc_text}\n")
                        else:
                            results.append(f"- [{w_up}] {title}")
            except Exception:
                pass

        # 2. Vector Dynamic Distance Banding Across Dedicated Buckets
        words = set(re.findall(r"\w+", text.lower()))
        significant_words = {w for w in words if len(w) > 2 and w not in SHALLOW_PROMPTS and w not in SHALLOWER_WORDS}

        if len(significant_words) >= 1:
            if model is None:
                model = get_fastembed()
            if model is not None:
                emb = list(model.embed([text[:2048]]))[0].tolist()

                domain_caps = {
                    "feature_dna": 3,
                    "behavioral_dna": 2,
                    "wisdom_dna": 2,
                    "inspiration_dna": 1,
                    "rdna": 1,
                    "loop_dna": 1,
                }
                domain_counts = {d: 0 for d in domain_caps}

                def check_in_band(dist, min_dist, has_kw):
                    base = (dist <= 0.76) or (dist <= min_dist + 0.08 and dist < 0.82) or (has_kw and dist <= 0.80)
                    if is_qq:
                        base = base or (dist <= 0.80)
                    return base

                # Feature DNA Bucket
                try:
                    col_feat = client.get_collection("feature_dna")
                    r_feat = col_feat.query(query_embeddings=[emb], n_results=6)
                    f_dists = r_feat.get("distances", [[]])[0]
                    if f_dists:
                        min_f = min(f_dists)
                        for i, dist in enumerate(f_dists):
                            if domain_counts["feature_dna"] >= domain_caps["feature_dna"]:
                                break
                            meta = r_feat["metadatas"][0][i]
                            fid = meta.get("feature_id") or r_feat["ids"][0][i].split("_")[0]
                            name = meta.get("name", "Feature")
                            status = meta.get("status", "ACTIVE")
                            if fid in seen_ids:
                                continue
                            has_kw = any(w in name.lower() for w in significant_words)
                            if check_in_band(dist, min_f, has_kw):
                                seen_ids.add(fid)
                                docs = r_feat.get("documents", [[]])[0]
                                doc_text = docs[i].strip() if i < len(docs) and docs[i] else ""
                                if doc_text:
                                    results.append(f"### [{fid}] {name} ({status})\n{doc_text}\n")
                                else:
                                    results.append(f"- [{fid}] {name} ({status})")
                                domain_counts["feature_dna"] += 1
                except Exception as e:
                    if hook_errors is not None:
                        hook_errors.append(f"feature_dna query failed: {e}")

                # Behavioral DNA (BKM / LAB / INFRA) Bucket
                try:
                    col_bkm = client.get_collection("behavioral_dna")
                    r_bkm = col_bkm.query(query_embeddings=[emb], n_results=6)
                    b_dists = r_bkm.get("distances", [[]])[0]
                    if b_dists:
                        min_b = min(b_dists)
                        for i, dist in enumerate(b_dists):
                            if domain_counts["behavioral_dna"] >= domain_caps["behavioral_dna"]:
                                break
                            meta = r_bkm["metadatas"][0][i]
                            name = meta.get("name", "Protocol")
                            bkm_id = meta.get("bkm_id")
                            if not bkm_id:
                                raw_id = r_bkm["ids"][0][i] if "ids" in r_bkm and i < len(r_bkm["ids"][0]) else ""
                                m_anchor = re.search(r"\b(BKM-\d+(?:\.\d+)?|LAB-\d+|FEAT-\d+|INFRA_[a-f0-9]+)\b", raw_id + " " + name, re.IGNORECASE)
                                if m_anchor:
                                    bkm_id = m_anchor.group(1).upper()
                                else:
                                    bkm_id = raw_id or "BKM"
                            if bkm_id in seen_ids:
                                continue
                            has_kw = any(w in name.lower() for w in significant_words)
                            if check_in_band(dist, min_b, has_kw):
                                seen_ids.add(bkm_id)
                                docs = r_bkm.get("documents", [[]])[0]
                                doc_text = docs[i].strip() if i < len(docs) and docs[i] else ""
                                if doc_text:
                                    results.append(f"### [{bkm_id}] {name}\n{doc_text}\n")
                                else:
                                    results.append(f"- [{bkm_id}] {name}")
                                domain_counts["behavioral_dna"] += 1
                except Exception as e:
                    if hook_errors is not None:
                        hook_errors.append(f"behavioral_dna query failed: {e}")

                # Wisdom DNA Bucket
                try:
                    col_wis = client.get_collection("wisdom_dna")
                    r_wis = col_wis.query(query_embeddings=[emb], n_results=4)
                    w_dists = r_wis.get("distances", [[]])[0]
                    if w_dists:
                        min_w = min(w_dists)
                        for i, dist in enumerate(w_dists):
                            if domain_counts["wisdom_dna"] >= domain_caps["wisdom_dna"]:
                                break
                            meta = r_wis["metadatas"][0][i]
                            wid = meta.get("wisdom_id") or r_wis["ids"][0][i]
                            title = meta.get("title", meta.get("name", "Wisdom"))
                            if wid in seen_ids:
                                continue
                            has_kw = any(w in title.lower() for w in significant_words)
                            if check_in_band(dist, min_w, has_kw):
                                seen_ids.add(wid)
                                docs = r_wis.get("documents", [[]])[0]
                                doc_text = docs[i].strip() if i < len(docs) and docs[i] else ""
                                if doc_text:
                                    results.append(f"### [{wid}] {title}\n{doc_text}\n")
                                else:
                                    results.append(f"- [{wid}] {title}")
                                domain_counts["wisdom_dna"] += 1
                except Exception as e:
                    if hook_errors is not None:
                        hook_errors.append(f"wisdom_dna query failed: {e}")

                # Inspiration / Philosophy DNA Bucket
                try:
                    col_ins = None
                    try:
                        col_ins = client.get_collection("inspiration_dna")
                    except Exception:
                        col_ins = client.get_collection("philosophy_dna")
                    if col_ins:
                        r_ins = col_ins.query(query_embeddings=[emb], n_results=3)
                        i_dists = r_ins.get("distances", [[]])[0]
                        if i_dists:
                            min_i = min(i_dists)
                            for i, dist in enumerate(i_dists):
                                if domain_counts["inspiration_dna"] >= domain_caps["inspiration_dna"]:
                                    break
                                meta = r_ins["metadatas"][0][i]
                                pid = meta.get("inspiration_id") or meta.get("wisdom_id") or r_ins["ids"][0][i]
                                title = meta.get("title", meta.get("name", "Inspiration"))
                                if pid in seen_ids:
                                    continue
                                has_kw = any(w in title.lower() for w in significant_words)
                                if check_in_band(dist, min_i, has_kw):
                                    seen_ids.add(pid)
                                    docs = r_ins.get("documents", [[]])[0]
                                    doc_text = docs[i].strip() if i < len(docs) and docs[i] else ""
                                    if doc_text:
                                        results.append(f"### [{pid}] {title}\n{doc_text}\n")
                                    else:
                                        results.append(f"- [{pid}] {title}")
                                    domain_counts["inspiration_dna"] += 1
                except Exception as e:
                    if hook_errors is not None:
                        hook_errors.append(f"inspiration_dna query failed: {e}")

                # Reverse DNA (RDNA HyDE Exemplar) Bucket
                try:
                    col_rdna = client.get_collection("rdna")
                    r_rdna = col_rdna.query(query_embeddings=[emb], n_results=3)
                    rd_dists = r_rdna.get("distances", [[]])[0]
                    if rd_dists:
                        min_rd = min(rd_dists)
                        for i, dist in enumerate(rd_dists):
                            if domain_counts["rdna"] >= domain_caps["rdna"]:
                                break
                            meta = r_rdna["metadatas"][0][i]
                            rid = meta.get("id") or r_rdna["ids"][0][i]
                            q_text = meta.get("question", meta.get("title", "Research Question"))
                            if rid in seen_ids:
                                continue
                            has_kw = any(w in q_text.lower() for w in significant_words)
                            if check_in_band(dist, min_rd, has_kw):
                                seen_ids.add(rid)
                                results.append(f"- [{rid}] HyDE Exemplar: {q_text}")
                                domain_counts["rdna"] += 1
                except Exception:
                    pass

                # Loop DNA Bucket
                try:
                    col_loop = client.get_collection("loop_dna")
                    r_loop = col_loop.query(query_embeddings=[emb], n_results=3)
                    l_dists = r_loop.get("distances", [[]])[0]
                    if l_dists:
                        min_l = min(l_dists)
                        for i, dist in enumerate(l_dists):
                            if domain_counts["loop_dna"] >= domain_caps["loop_dna"]:
                                break
                            meta = r_loop["metadatas"][0][i]
                            lid = meta.get("loop_id") or r_loop["ids"][0][i]
                            name = meta.get("name", meta.get("title", "Feedback Loop"))
                            if lid in seen_ids:
                                continue
                            has_kw = any(w in name.lower() for w in significant_words)
                            if check_in_band(dist, min_l, has_kw):
                                seen_ids.add(lid)
                                docs = r_loop.get("documents", [[]])[0]
                                doc_text = docs[i].strip() if i < len(docs) and docs[i] else ""
                                if doc_text:
                                    results.append(f"### [{lid}] {name}\n{doc_text}\n")
                                else:
                                    results.append(f"- [{lid}] {name}")
                                domain_counts["loop_dna"] += 1
                except Exception:
                    pass
    except Exception as e:
        if hook_errors is not None:
            hook_errors.append(f"ClaraDB probe exception: {e}")
        for l_id in extract_literal_ids(text):
            if l_id not in seen_ids:
                seen_ids.add(l_id)
                results.append(l_id)

    return results


def probe_sprint_dna(
    text: str,
    client=None,
    limit: int = 2,
    seen_ids: set = None,
    hook_errors: list = None,
):
    """[FEAT-557] Query dedicated sprint_dna collection on :8001."""
    if not bool(_SPRINT_KEYWORD_RE.search(text)):
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
                    (
                        ln.strip()
                        for ln in docs[i].splitlines()
                        if ln.strip()
                        and not ln.startswith("STORY")
                        and not ln.startswith("SPRINT")
                    ),
                    "",
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
        if hook_errors is not None:
            hook_errors.append(f"sprint_dna query failed: {e}")
        return []


def probe_icm(
    text: str,
    project: str,
    is_qq: bool = False,
    limit: int = 2,
    hook_errors: list = None,
):
    """[LAB-019] In-process SQLite FTS5 query with full uncropped summary."""
    words = [re.sub(r"[^\w-]", "", w) for w in text.lower().split() if len(w) > 2]
    words = [w for w in words if w and w not in SHALLOWER_WORDS and w not in SHALLOW_PROMPTS]
    if len(words) < 1:
        return []

    db_path = os.path.expanduser("~/.local/share/icm/memories.db")
    if not os.path.exists(db_path):
        return []

    try:
        import sqlite3

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.1)
        cursor = conn.cursor()

        fts_query = " OR ".join(f'"{w}"' for w in words[:6])
        cursor.execute(
            """
            SELECT m.topic, m.summary
            FROM memories_fts f
            JOIN memories m ON f.rowid = m.rowid
            WHERE memories_fts MATCH ? AND m.summary NOT LIKE '%[REMOVED]%'
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (fts_query, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        return [f"- ({r[0]}) {r[1]}" for r in rows if r and r[1]]
    except Exception as e:
        if hook_errors is not None:
            hook_errors.append(f"icm direct SQLite probe error: {e}")
        return []


def execute_ambient_recall(payload: dict) -> dict:
    """[FEAT-600 / LAB-019 / BKM-060] Core ambient memory & knowledge recall engine.
    
    Can be called directly within a resident daemon (e.g. Foyer / lab-attendant :8765)
    with warm in-memory FastEmbed & ChromaDB instances, or via CLI subprocess.
    """
    start_time = time.perf_counter()
    hook_errors = []

    # Sisyphus-Junior and swarm delegation bypass
    agent_name = (payload.get("agent") or payload.get("agentName") or "").lower()
    session_title = (payload.get("sessionTitle") or payload.get("title") or "").lower()
    user_input_raw = (
        payload.get("userMessage")
        or payload.get("prompt")
        or payload.get("last_user_message")
        or ""
    )
    if (
        "junior" in agent_name
        or "junior" in session_title
        or "air" in agent_name
        or any(
            marker in user_input_raw
            for marker in [
                "[STORY DELEGATION TARGET",
                "[TASK:",
                "[ORCHESTRATION INSTRUCTIONS",
                "[SPOON-FED TASK",
                "[MOMUS:",
                "[LIBRARIAN:",
            ]
        )
    ):
        return {"injectSteps": []}

    inv_num = payload.get("invocationNum", 1)
    workspace_paths = payload.get("workspacePaths", [])
    project = os.path.basename(workspace_paths[0]) if workspace_paths else "Dev_Lab"

    # Turn 1: Session Start Recency Flush + Wake-Up Pack
    if inv_num == 1:
        session_start_lines = []
        try:
            import subprocess

            res = subprocess.run(
                ["icm", "wake-up", "-t", "200", "-p", project],
                capture_output=True,
                text=True,
                timeout=4,
            )
            if res.returncode == 0 and res.stdout.strip():
                clean_lines = [
                    l for l in res.stdout.strip().split("\n") if "[REMOVED]" not in l
                ]
                session_start_lines.append("\n".join(clean_lines))
        except Exception as e:
            hook_errors.append(f"icm wake-up error: {e}")

        recent_mems = get_recent_memories(limit=4)
        if recent_mems:
            session_start_lines.append(
                "\n## Recently Learned & Latest Sprint Decisions (Last Session)"
            )
            for m in recent_mems:
                session_start_lines.append(
                    f"- [{m['created']}] ({m['topic']}) {m['summary']}"
                )

        if session_start_lines:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            breadcrumb = f"> 🧬 **Grounding**: Session Wake-Up ({len(recent_mems)} recent memories • {elapsed_ms:.1f}ms)"
            session_start_lines.insert(0, f"[Grounding Header: {breadcrumb}]")
            return {
                "injectSteps": [
                    {"ephemeralMessage": "\n".join(session_start_lines)}
                ]
            }
        else:
            return {"injectSteps": []}

    # Subsequent Turns: Gating and Multi-Item Segmentation
    transcript_path = payload.get("transcriptPath")
    if transcript_path and os.path.exists(transcript_path):
        is_start, last_prompt = is_turn_start(transcript_path)
        if not is_start:
            return {"injectSteps": []}
        cleaned = clean_prompt(last_prompt)
    else:
        cleaned = clean_prompt(user_input_raw)

    if not cleaned:
        return {"injectSteps": []}

    is_qq = cleaned.lower().startswith("qq")
    search_query = re.sub(r"^qq[:!\s]*", "", cleaned, flags=re.IGNORECASE).strip()

    chroma_client = get_chroma_client()
    fastembed_model = get_fastembed()

    seen_ids = set()
    ambient_lines = []
    all_summary_clara = []
    all_summary_icm = []

    segments = []
    try:
        segments = extract_prompt_segments(search_query)
    except Exception as seg_e:
        hook_errors.append(f"Segmentation regex failed: {seg_e}")
        segments = [{"id": "1", "label": "Query", "text": search_query}]

    num_segs = len(segments)
    multi_item_mode = num_segs > 1

    if multi_item_mode:
        ambient_lines.append(
            f"[Ambient Grounding: Multi-Item Intent Resolution ({num_segs} Segments)]"
        )

    from concurrent.futures import ThreadPoolExecutor

    def process_single_segment(seg):
        seg_text = seg["text"]
        seg_lines = []
        seg_clara_summary = []
        seg_icm_summary = []
        seg_errors = []
        seg_seen_ids = set()

        # 1. Dedicated DNA Buckets with full document text
        try:
            clara_hits = probe_claradb(
                seg_text,
                client=chroma_client,
                model=fastembed_model,
                is_qq=is_qq,
                limit=10,
                seen_ids=seg_seen_ids,
                hook_errors=seg_errors,
            )
            for h in clara_hits:
                match = re.search(r"\[(.*?)\]", h)
                if match:
                    seg_clara_summary.append(match.group(1))
                if multi_item_mode:
                    if h.startswith("### "):
                        seg_lines.append(f"  {h}")
                    else:
                        seg_lines.append(f"  - Clara: {h[2:]}")
                else:
                    seg_lines.append(h)
        except Exception as ce:
            seg_errors.append(f"Clara segment probe failed ({seg['label']}): {ce}")

        # 2. Sprint DNA probe for segment
        try:
            sprint_hits = probe_sprint_dna(
                seg_text,
                client=chroma_client,
                limit=2,
                seen_ids=seg_seen_ids,
                hook_errors=seg_errors,
            )
            for sh in sprint_hits:
                if multi_item_mode:
                    seg_lines.append(f"  - Sprint: {sh[2:]}")
                else:
                    seg_lines.append(sh)
        except Exception as se:
            seg_errors.append(f"Sprint segment probe failed ({seg['label']}): {se}")

        # 3. In-process SQLite Memory probe for segment
        try:
            icm_hits = probe_icm(
                seg_text,
                project=project,
                is_qq=is_qq,
                limit=2,
                hook_errors=seg_errors,
            )
            for ih in icm_hits:
                m_top = re.search(r"\((.*?)\)", ih)
                if m_top:
                    seg_icm_summary.append(m_top.group(1))
                if multi_item_mode:
                    seg_lines.append(f"  - ICM: {ih[2:]}")
                else:
                    seg_lines.append(ih)
        except Exception as ie:
            seg_errors.append(f"ICM segment probe failed ({seg['label']}): {ie}")

        return {
            "seg": seg,
            "seg_lines": seg_lines,
            "clara_summary": seg_clara_summary,
            "icm_summary": seg_icm_summary,
            "errors": seg_errors,
            "seen_ids": seg_seen_ids,
        }

    # Parallelize segment processing across threads
    if num_segs > 1:
        with ThreadPoolExecutor(max_workers=min(6, num_segs)) as pool:
            seg_results = list(pool.map(process_single_segment, segments))
    else:
        seg_results = [process_single_segment(segments[0])]

    for s_res in seg_results:
        seg = s_res["seg"]
        seg_lines = s_res["seg_lines"]
        all_summary_clara.extend(s_res["clara_summary"])
        all_summary_icm.extend(s_res["icm_summary"])
        hook_errors.extend(s_res["errors"])
        seen_ids.update(s_res["seen_ids"])

        if seg_lines:
            if multi_item_mode:
                snippet = seg["text"][:50] + ("..." if len(seg["text"]) > 50 else "")
                ambient_lines.append(f"▸ {seg['label']} (\"{snippet}\"):")
                ambient_lines.extend(seg_lines)
            else:
                ambient_lines.append("[ClaraDB Anchors & Matches]")
                ambient_lines.extend(seg_lines)

    # Handover Playbook Reminder
    query_lower = search_query.lower()
    if any(
        k in query_lower
        for k in (
            "delegate",
            "delegation",
            "bkm-049",
            "bkm049",
            "swarm",
            "handover",
            "retry",
        )
    ):
        ambient_lines.append("[💡 PLAYBOOK AUDIT REMINDER]")
        ambient_lines.append(
            "  - Read OPENAGENT_HANDOVER_PLAYBOOK.md to avoid common pitfalls: MCP bloat, agent inversion, root indexing, concurrency deadlocks."
        )

    if not ambient_lines:
        literal_fallbacks = extract_literal_ids(search_query)
        if literal_fallbacks:
            ambient_lines.append("[Direct Literal Code/Protocol Anchors]")
            ambient_lines.extend(literal_fallbacks)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    warn_threshold_ms = float(os.environ.get("HOOK_WARN_THRESHOLD_MS", 600.0))

    if elapsed_ms > warn_threshold_ms:
        lat_msg = f"Hook execution took {elapsed_ms:.1f}ms (threshold: {warn_threshold_ms:.0f}ms)"
        hook_errors.append(lat_msg)
        try:
            sys.stderr.write(
                f"\n\033[33m⚠️ [Hook Latency Warning]\033[0m {lat_msg}\n"
            )
            sys.stderr.flush()
        except Exception:
            pass

    if hook_errors:
        err_summary = "; ".join(hook_errors[:3])
        warning_header = f"[⚠️ AMBIENT HOOK WARNING: Degraded Execution — Hook notice/error(s): {err_summary}]"
        ambient_lines.insert(0, warning_header)

    if ambient_lines:
        anchors = list(seen_ids)
        breadcrumb = f"> 🧬 **Grounding**: {' '.join([f'[{a}]' for a in anchors[:4]]) if anchors else 'Nominal'} ({len(anchors)} hits • {elapsed_ms:.1f}ms)"
        ambient_lines.insert(0, f"[Grounding Header: {breadcrumb}]")

        return {"injectSteps": [{"ephemeralMessage": "\n".join(ambient_lines)}]}
    else:
        return {"injectSteps": []}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        sys.stderr.write(
            f"\n\033[31m⚠️ [Hook Error / Degraded Mode]\033[0m Invalid hook payload on stdin: {e}\n"
        )
        print(json.dumps({"injectSteps": []}))
        return

    res = execute_ambient_recall(payload)
    print(json.dumps(res))


if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_e:
        err_text = f"Fatal unhandled exception in ambient_recall: {fatal_e}"
        print(
            json.dumps(
                {
                    "injectSteps": [
                        {
                            "ephemeralMessage": f"[⚠️ AMBIENT HOOK WARNING: Fatal hook error occurred: {err_text}]"
                        }
                    ]
                }
            )
        )
