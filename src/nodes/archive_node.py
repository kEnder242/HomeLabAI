import os
import json
import logging
import datetime
import glob
import subprocess
import chromadb
import aiohttp
from chromadb.utils import embedding_functions

from infra.montana import reclaim_logger

# [FEAT-304] Protocol Hardening: Ensure logs do not corrupt the MCP JSON-RPC pipe
reclaim_logger(role="ARCHIVE")

try:
    from nodes.loader import BicameralNode
except ImportError:
    from loader import BicameralNode

# --- Configuration ---
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
LAB_DIR = os.path.expanduser("~/Dev_Lab/HomeLabAI")
DRAFTS_DIR = os.path.join(WORKSPACE_DIR, "docs/drafts")
WHITEBOARD_DIR = os.path.join(WORKSPACE_DIR, "whiteboard")
FIELD_NOTES_DIR = os.path.join(WORKSPACE_DIR, "field_notes")
DATA_DIR = os.path.join(FIELD_NOTES_DIR, "data")
RUFF_PATH = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/ruff"
STYLE_CSS = os.path.join(FIELD_NOTES_DIR, "style.css")
SEMANTIC_MAP_FILE = os.path.join(DATA_DIR, "semantic_map.json")

# [Task 3.1] The Clipboard: Session-scoped context cache
SESSION_CLIPBOARD = []
CLIPBOARD_CHAR_LIMIT = 8000 # [Task 2.3] Memory-OS: Context ceiling

def get_style_key():
    """[FEAT-267] Dynamic Key Discovery for Lab REST calls."""
    import hashlib
    if not os.path.exists(STYLE_CSS):
        return "missing"
    with open(STYLE_CSS, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_STREAM = "short_term_stream"
COLLECTION_WISDOM = "long_term_wisdom"
COLLECTION_DNA = "behavioral_dna"

# Chroma Setup
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def get_safe_collection(name):
    try:
        return chroma_client.get_or_create_collection(name=name, embedding_function=ef)
    except ValueError:
        return chroma_client.get_or_create_collection(name=name)


stream = get_safe_collection(COLLECTION_STREAM)
wisdom = get_safe_collection(COLLECTION_WISDOM)
dna = get_safe_collection(COLLECTION_DNA)

# Ensure paths exist
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(WHITEBOARD_DIR, exist_ok=True)

# Logging
logging.basicConfig(level=logging.ERROR)

ARCHIVE_SYSTEM_PROMPT = (
    "You are the Archive Node. You have access to the Filing Cabinet. "
    "Your duty is to list and read documents accurately. "
    "You also have a 'whiteboard' folder for sandbox writing."
)

node = BicameralNode("ArchiveNode", ARCHIVE_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def create_followup_file(topic_filename: str, context: str) -> str:
    """
    [Task 3.4] The Collaborative Ledger: Instantiates a physical build-up file in whiteboard.
    Ensures the filename ends in .md and populates initial context.
    [Task 3.6] RAG Pointers: Use pointers (e.g. [Source: 2024_02.json]) instead of full text to save headroom.
    """
    if not topic_filename.endswith(".md"):
        topic_filename += ".md"
    
    path = os.path.join(WHITEBOARD_DIR, topic_filename)
    
    # [Task 3.5] Append-only by default: If file exists, we append context
    mode = "a" if os.path.exists(path) else "w"
    try:
        with open(path, mode) as f:
            if mode == "w":
                f.write(f"# {topic_filename.replace('.md', '').upper()} RESEARCH LEDGER\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"## Context Entry ({datetime.datetime.now().strftime('%H:%M')})\n")
            f.write(f"{context}\n\n---\n")
        
        return f"✅ Follow-up ledger created/updated: whiteboard/{topic_filename}"
    except Exception as e:
        return f"❌ Failed to create ledger: {e}"


@mcp.tool()
async def scribble_to_clipboard(content: str) -> str:
    """
    [Task 3.1] The Clipboard: Scribbles high-value context to the session-scoped cache.
    [Task 2.3] Memory-OS: Implements character-aware eviction.
    """
    global SESSION_CLIPBOARD
    if content not in SESSION_CLIPBOARD:
        SESSION_CLIPBOARD.append(content)
        
        # [Task 2.3] Memory-OS: Evict until under char limit
        while sum(len(c) for c in SESSION_CLIPBOARD) > CLIPBOARD_CHAR_LIMIT:
            SESSION_CLIPBOARD.pop(0) # FIFO Eviction of oldest context
            
        total_len = sum(len(c) for c in SESSION_CLIPBOARD)
        return f"✅ Scribbled to clipboard. ({len(SESSION_CLIPBOARD)} segments, {total_len} chars active)"
    return "Segment already resident in clipboard."


@mcp.tool()
async def read_clipboard() -> str:
    """
    [Task 3.1] The Clipboard: Retrieves the accumulated session context.
    """
    if not SESSION_CLIPBOARD:
        return "Clipboard is empty."
    
    combined = "\n---\n".join(SESSION_CLIPBOARD)
    return f"[SESSION_CLIPBOARD]:\n{combined}"


@mcp.tool()
async def clear_clipboard() -> str:
    """
    [Task 3.1] The Clipboard: Purges the session-scoped cache.
    """
    global SESSION_CLIPBOARD
    SESSION_CLIPBOARD = []
    return "✅ Clipboard cleared."


@mcp.tool()
async def list_cabinet() -> str:
    """The Filing Cabinet: Lists all openable technical artifacts (JSON and HTML)."""
    try:
        all_items = []
        # [FOLDER-FIRST] Restricting view to active shared folders.
        # Raw JSON logs are kept in background for RAG usage only.
        htmls = glob.glob(os.path.join(FIELD_NOTES_DIR, "*.html"))
        all_items.extend([os.path.basename(f) for f in htmls])
        drafts = [
            f"drafts/{os.path.basename(f)}"
            for f in glob.glob(os.path.join(DRAFTS_DIR, "*"))
        ]
        all_items.extend(drafts)
        whiteboard = [
            f"whiteboard/{os.path.basename(f)}"
            for f in glob.glob(os.path.join(WHITEBOARD_DIR, "*"))
        ]
        all_items.extend(whiteboard)
        return json.dumps(sorted(list(set(all_items))))
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def read_document(filename: str) -> str:
    """Reads content from workspace, drafts, whiteboard, or data folders."""
    # [FIX] Handle directory-prefixed filenames from UI
    if "/" in filename:
        # Check if the prefix is valid
        parts = filename.split("/", 1)
        prefix, actual_name = parts[0], parts[1]
        if prefix == "drafts":
            filename = actual_name
        elif prefix == "whiteboard":
            filename = actual_name

    search_paths = [
        os.path.join(DRAFTS_DIR, filename),
        os.path.join(WHITEBOARD_DIR, filename),
        os.path.join(DATA_DIR, filename),
        os.path.join(FIELD_NOTES_DIR, filename),
        os.path.join(WORKSPACE_DIR, filename),
        os.path.join(LAB_DIR, filename),
    ]
    for p in search_paths:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, "r") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading {filename}: {e}"
    return f"Error: File '{filename}' not found."


@mcp.tool()
async def patch_file(filename: str, diff: str, soft_fail: bool = False) -> str:
    """
    [BKM-012] The Ultimate Patcher: Applies a Unified Diff to a workspace file.
    diff: Standard unified format.
    soft_fail: If True, persists changes even if linting fails.
    """
    # 1. Resolve path
    target_path = None
    search_folders = [
        DRAFTS_DIR,
        WHITEBOARD_DIR,
        FIELD_NOTES_DIR,
        WORKSPACE_DIR,
        LAB_DIR,
    ]
    for folder in search_folders:
        p = os.path.join(folder, filename)
        if os.path.exists(p):
            target_path = p
            break

    if not target_path:
        return f"Error: File '{filename}' not found in searchable paths."

    # 2. Safety: Save original content for rollback
    with open(target_path, "r") as f:
        original_content = f.read()

    # 3. Write diff to temporary patch file
    patch_path = target_path + ".patch"
    with open(patch_path, "w") as f:
        f.write(diff)

    try:
        # 4. Apply Patch
        res = subprocess.run(
            ["patch", "-u", target_path, patch_path], capture_output=True, text=True
        )
        if res.returncode != 0:
            return f"Patch failed for {filename}:\n{res.stderr}"

        # 5. Lint-Gate
        if target_path.endswith(".py"):
            # [SWEET SPOT] Focus on functional integrity and imports.
            # Ignore E501 (Line Length) to prevent style noise from drowning out logic errors.
            l_res = subprocess.run(
                [
                    RUFF_PATH,
                    "check",
                    target_path,
                    "--select",
                    "E,F,W",
                    "--ignore",
                    "E501",
                ],
                capture_output=True,
                text=True,
            )
            if l_res.returncode != 0:
                msg = f"LINT ERROR DETECTED IN {filename} - PLEASE FIX:\n{l_res.stdout}"
                if soft_fail:
                    # Return success status but with high-visibility warning message
                    return f"⚠️ APPLIED WITH LINT ERRORS (SOFT FAIL):\n{msg}"
                else:
                    # Rollback
                    with open(target_path, "w") as f:
                        f.write(original_content)
                    return f"❌ ROLLBACK TRIGGERED DUE TO LINT FAILURE:\n{msg}"

        return f"✅ Surgically patched {filename} successfully."

    except Exception as e:
        return f"Critical error during patching: {e}"
    finally:
        if os.path.exists(patch_path):
            os.remove(patch_path)


@mcp.tool()
async def peek_related_notes(keyword: str) -> str:
    """RLM Research Pattern: Follows technical breadcrumbs using Hybrid Keyword Search."""
    try:
        # Use the established keyword_search for high-fidelity matching
        results = keyword_search(keyword, limit=10)
        
        if not results:
            # Fallback to search_index.json for broad categorization
            index_path = os.path.join(FIELD_NOTES_DIR, "search_index.json")
            if os.path.exists(index_path):
                with open(index_path, "r") as f:
                    index = json.load(f)
                matches = []
                k_lower = keyword.lower()
                for key in index.keys():
                    if k_lower in key.lower():
                        matches.extend(index[key])
                if matches:
                    return f"Related technical breadcrumbs (Index): {', '.join(list(set(matches))[:10])}"
            
            return f"No notes found relating to '{keyword}'."
        
        breadcrumbs = []
        for doc_id, meta in results:
            src = meta.get("source", "Unknown")
            breadcrumbs.append(f"{doc_id} (in {src})")
            
        return f"Related technical breadcrumbs (Hybrid): {', '.join(breadcrumbs)}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def create_event_for_learning(topic: str, context: str, successful: bool) -> str:
    """The Pedagogue's Ledger: Logs teaching moments or failures."""
    try:
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "topic": topic,
            "context": context,
            "successful": successful,
        }
        l_path = os.path.join(DATA_DIR, "learning_ledger.jsonl")
        with open(l_path, "a") as f:
            f.write(json.dumps(event) + "\n")
        return f"Event logged: {topic} (Success: {successful})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def write_draft(filename: str, content: str) -> str:
    """Stage a new technical artifact or BKM."""
    path = os.path.join(DRAFTS_DIR, filename)
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Draft saved to {filename}."
    except Exception as e:
        return f"Error saving draft: {e}"


@mcp.tool()
async def write_to_whiteboard(filename: str, content: str) -> str:
    """Write to the sandbox whiteboard. Use this for scratchpad work or thoughts."""
    path = os.path.join(WHITEBOARD_DIR, filename)
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Content written to whiteboard/{filename}."
    except Exception as e:
        return f"Error writing to whiteboard: {e}"


@mcp.tool()
async def prune_insights(
    start_date: str, end_date: str, pattern: str, field: str = "summary"
) -> str:
    """[FEAT-073] Surgically redacts or trims data from note summaries."""
    import re

    try:
        s_date = datetime.datetime.strptime(start_date, "%Y-%m")
        e_date = datetime.datetime.strptime(end_date, "%Y-%m")
        modified_files = []
        curr = s_date
        while curr <= e_date:
            fname = f"{curr.year}_{curr.month:02d}.json"
            fpath = os.path.join(DATA_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "r") as f:
                    data = json.load(f)
                changed = False
                for entry in data:
                    if field in entry and isinstance(entry[field], str):
                        original = entry[field]
                        entry[field] = re.sub(pattern, "[REDACTED]", original)
                        if entry[field] != original:
                            changed = True
                if changed:
                    with open(fpath, "w") as f:
                        json.dump(data, f, indent=2)
                    modified_files.append(fname)
            if curr.month == 12:
                curr = datetime.datetime(curr.year + 1, 1, 1)
            else:
                curr = datetime.datetime(curr.year, curr.month + 1, 1)
        return f"Pruning complete. Modified {len(modified_files)} files."
    except Exception as e:
        return f"Pruning failed: {e}"


@mcp.tool()
async def select_file(filename: str) -> str:
    """[FEAT-074] Workbench: Instructs the UI to open a specific file in the editor."""
    return json.dumps({"type": "select_file", "filename": filename})


@mcp.tool()
async def notify_file_open(filename: str) -> str:
    """[FEAT-074] Workbench: Notifies the mice that the user has opened a file."""
    logging.info(f"[WORKBENCH] User opened: {filename}")
    return f"Acknowledged. Monitoring activity on {filename}."


@mcp.tool()
async def save_interaction(query: str, response: str) -> str:
    """Saves a conversation turn to the short-term vector stream."""
    try:
        ts = datetime.datetime.now().isoformat()
        doc = f"User: {query}\nAssistant: {response}"
        stream.add(
            documents=[doc],
            metadatas=[{"timestamp": ts, "type": "turn"}],
            ids=[f"turn_{ts}"],
        )
        return "Interaction secured in stream."
    except Exception as e:
        return f"Failed to save: {e}"


@mcp.tool()
async def dream(summary: str, sources: list[str]) -> str:
    """
    Consolidates synthesized wisdom into long-term memory and purges sources.
    Input: High-density narrative summary and the list of raw IDs processed.
    """
    try:
        ts = datetime.datetime.now().isoformat()
        # 1. Store the high-density wisdom
        wisdom.add(
            documents=[summary],
            metadatas=[{"timestamp": ts, "type": "insight", "count": len(sources)}],
            ids=[f"wisdom_{ts}"],
        )
        # 2. Purge the raw chaotic memories
        if sources:
            stream.delete(ids=sources)
        return f"Dreaming complete. Consolidated {len(sources)} logs."
    except Exception as e:
        return f"Dream failed: {e}"


MEMO_CACHE = os.path.join(DATA_DIR, "memo_cache.json")

@mcp.tool()
async def get_observational_memo(topic: str = None, year: str = None) -> str:
    """
    [FEAT-266.9] Memo Layer: Retrieves pre-synthesized observations.
    Useful for high-level grounding before deep retrieval.
    """
    if not os.path.exists(MEMO_CACHE):
        return "No observational memos found."
        
    try:
        with open(MEMO_CACHE, "r") as f:
            data = json.load(f)
            
        if year and year in data.get("years", {}):
            return f"[MEMO: {year}]: {data['years'][year]}"
            
        if topic:
            # Simple keyword match for topics
            for t, content in data.get("topics", {}).items():
                if topic.lower() in t.lower():
                    return f"[MEMO: {t}]: {content}"
                    
        return "No matching memo for this context."
    except Exception as e:
        return f"Memo retrieval error: {e}"

@mcp.tool()
async def scribble_note(query: str, response: str) -> str:
    """Caches a response semantically for future recall."""
    try:
        ts = datetime.datetime.now().isoformat()
        # COLLECTIONS_CACHE not defined, using default logic
        # For simplicity, adding to stream with a cache tag
        stream.add(
            documents=[response],
            metadatas=[{"query": query, "timestamp": ts, "type": "cache"}],
            ids=[f"cache_{ts}"],
        )
        return "Note scribbled semantically."
    except Exception as e:
        return f"Error: {e}"


def rrf_fuse(results_list, k=60):
    """
    [Task 3.2] Reciprocal Rank Fusion: Merges multiple search result lists.
    results_list: list of lists of (id, metadata)
    """
    scores = {}
    metadata_map = {}
    for results in results_list:
        for rank, (doc_id, meta) in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            if doc_id not in metadata_map:
                metadata_map[doc_id] = meta
    
    # Sort by fused score
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(doc_id, metadata_map[doc_id]) for doc_id, _ in sorted_ids]


def keyword_search(query, limit=10):
    """
    [Task 3.2] Exact-match search for acronyms and specific terms.
    Scans raw JSON archives.
    """
    # Extract candidate acronyms (all caps, 3+ chars)
    import re
    acronyms = re.findall(r"\b[A-Z]{3,}\b", query)
    # Also extract non-stop words
    terms = [t for t in query.split() if len(t) > 4 and t.upper() not in acronyms]
    
    candidates = acronyms + terms
    if not candidates:
        return []

    results = []
    seen_ids = set()
    
    # Search in DATA_DIR
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    for f_path in json_files:
        try:
            with open(f_path, "r") as f:
                data = json.load(f)
                if not isinstance(data, list): continue
                
                for entry in data:
                    text_blob = str(entry).lower()
                    for c in candidates:
                        if c.lower() in text_blob:
                            e_id = entry.get("id") or entry.get("filename") or str(entry.get("date", ""))
                            if e_id and e_id not in seen_ids:
                                results.append((e_id, {"source": os.path.basename(f_path), "text": str(entry)}))
                                seen_ids.add(e_id)
                                break
                    if len(results) >= limit: break
        except Exception:
            continue
        if len(results) >= limit: break
        
    return results


@mcp.tool()
async def get_context(query: str, n_results: int = 3, domain: str = None) -> str:
    """
    [FEAT-117] Multi-Stage Retrieval: Discovery -> Acquisition.
    Stage 1: ChromaDB identifies the metadata anchor.
    Stage 2: ArchiveNode retrieves the raw JSON truth from filesystem.
    [Task 3.1] The Clipboard: Integrates session context and expands neighborhoods.
    """
    try:
        # [Task 3.1] Integrate session clipboard early
        combined_context = []
        if SESSION_CLIPBOARD:
            combined_context.append("[SESSION_CLIPBOARD]:\n" + "\n---\n".join(SESSION_CLIPBOARD))

        # [FEAT-117] Hard Year Filtering (Post-Filter)
        import re
        # Support years from 1990 to 2029
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        target_year = year_match.group(1) if year_match else None

        # [Task 2.1] Memo Integration: Check for high-level observations first
        memo = await get_observational_memo(topic=query if not target_year else None, year=target_year)
        if "[MEMO:" in memo:
            combined_context.append(memo)
        
        # [FEAT-088] Semantic Fallback
        if not target_year:
            logging.info("[ARCHIVE] No temporal anchor in query. Performing agnostic semantic search.")
        
        fetch_limit = n_results * 5 if target_year else n_results
        if target_year:
            logging.info(f"[ARCHIVE] Applying Hard Year Post-Filter: {target_year}")

        # Stage 1: Hybrid Discovery (RRF)
        vector_results = []
        res_w = wisdom.query(query_texts=[query], n_results=fetch_limit)
        for i, doc in enumerate(res_w.get("documents", [[]])[0]):
            meta = res_w.get("metadatas", [[]])[0][i]
            vector_results.append((doc[:100], {**meta, "text_anchor": doc}))

        res_s = stream.query(query_texts=[query], n_results=fetch_limit)
        for i, doc in enumerate(res_s.get("documents", [[]])[0]):
            meta = res_s.get("metadatas", [[]])[0][i]
            vector_results.append((doc[:100], {**meta, "text_anchor": doc}))
            
        k_results = keyword_search(query, limit=fetch_limit)
        
        # Reciprocal Rank Fusion
        fused_results = rrf_fuse([vector_results, k_results])

        if not fused_results and not SESSION_CLIPBOARD:
            return json.dumps({"text": "No relevant artifacts found in neural archives.", "sources": []})
        elif not fused_results:
             return json.dumps({"text": "\n\n".join(combined_context), "sources": []})

        # Stage 2: Raw Acquisition (Multi-Stage Discovery)
        full_truths = []
        source_files = []
        
        # [FEAT-126/127] Yearly Summary Injection
        if target_year:
            years_to_peek = [str(int(target_year) - 1), target_year]
            for y in years_to_peek:
                summary_file = f"{y}.json"
                summary_path = os.path.join(DATA_DIR, summary_file)
                if os.path.exists(summary_path):
                    if summary_file not in source_files:
                        source_files.append(summary_file)
                    try:
                        with open(summary_path, 'r') as f:
                            summary_data = json.load(f)
                            # Extract high-rank anchors
                            high_rank = sorted([e for e in summary_data if e.get('rank', 0) >= 3], 
                                             key=lambda x: x.get('rank', 0), reverse=True)[:2]
                            for entry in high_rank:
                                full_truths.append(
                                    f"[STRATEGIC SUMMARY {y}]: {entry.get('summary')} "
                                    f"(Gem: {entry.get('technical_gem', 'N/A')})"
                                )
                    except Exception:
                         pass

        domain_keywords = {
            "exp_tlm": ["telemetry", "monitor", "prometheus", "grafana", "rapl", "msr", "power", "thermal", "load", "sensory", "logging", "metric", "dcgm", "gpu", "nvml"],
            "exp_bkm": ["bkm", "validation", "test", "verification", "verify", "spec", "method", "guide", "setup", "procedure", "config", "manual", "checklist"],
            "exp_for": ["forensic", "post-mortem", "post_mortem", "crash", "triage", "hang", "error", "abort", "fail", "debug", "logs", "analysis", "incident"]
        }

        # Collect candidates
        candidates = []
        for doc_id, meta in fused_results:
            ts = str(meta.get("timestamp") or meta.get("date") or meta.get("source", ""))
            doc_anchor = meta.get("text_anchor", meta.get("text", ""))
            
            if target_year and target_year not in ts:
                continue
            candidates.append((doc_id, meta, ts, doc_anchor))

        # MCompassRAG: Domain-Guided Paragraph Filtering
        if not domain:
            status_path = os.path.join(DATA_DIR, "status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        status_data = json.load(f)
                        domain = status_data.get("active_domain")
                        if domain:
                            logging.info(f"[MCompassRAG] Read active domain fallback from status.json: {domain}")
                except Exception as e:
                    logging.warning(f"[MCompassRAG] Failed to read active domain fallback: {e}")

        if domain and domain in domain_keywords:
            keywords = domain_keywords[domain]
            filtered = []
            for doc_id, meta, ts, doc_anchor in candidates:
                doc_anchor_low = str(doc_anchor).lower()
                if any(kw in doc_anchor_low for kw in keywords):
                    filtered.append((doc_id, meta, ts, doc_anchor))
            
            if filtered:
                logging.info(f"[MCompassRAG] Restricting search space to {len(filtered)}/{len(candidates)} paragraphs for domain {domain}.")
                candidates = filtered
            else:
                logging.info(f"[MCompassRAG] Domain {domain} filter yielded 0 matches. Falling back to unfiltered space.")

        matched_count = 0
        expansion_triggered = False

        for doc_id, meta, ts, doc_anchor in candidates:
            if matched_count >= n_results:
                break
                
            matched_count += 1
            target_file = None
            if ts:
                if ts.endswith(".json"):
                    target_file = ts
                elif len(ts) >= 7:
                    year_month = ts[:7].replace("-", "_")
                    target_file = f"{year_month}.json"

                if target_file and os.path.exists(os.path.join(DATA_DIR, target_file)):
                    # [FEAT-117/306] Bridge to raw JSON truth
                    file_path = os.path.join(DATA_DIR, target_file)
                    with open(file_path, "r") as f:
                        file_data = json.load(f)
                    
                    # Neighborhood Expansion
                    if not expansion_triggered:
                        for idx, entry in enumerate(file_data):
                            if doc_anchor[:50] in str(entry):
                                neighbors = []
                                if idx > 0: neighbors.append(file_data[idx-1])
                                neighbors.append(file_data[idx]) # Self
                                if idx < len(file_data) - 1: neighbors.append(file_data[idx+1])
                                
                                for n in neighbors:
                                    n_text = f"[NEIGHBORHOOD_EXPANSION Source: {target_file}]: {json.dumps(n)}"
                                    if n_text not in SESSION_CLIPBOARD:
                                        SESSION_CLIPBOARD.append(n_text)
                                
                                logging.info(f"[ARCHIVE] Neighborhood expansion triggered for {target_file}")
                                expansion_triggered = True
                                break

                    full_truths.append(
                        f"[ACQUISITION Source: {target_file}]: "
                        f"Document anchor: {doc_anchor[:200]}... "
                        f"Use 'read_document(\"{target_file}\")' to see the physical evidence."
                    )
                    if target_file not in source_files:
                        source_files.append(target_file)
                    continue

            full_truths.append(f"[DISCOVERY Anchor: {ts}]: {doc_anchor[:200]}...")

        # Combine Clipboard + New Truths
        final_text = "\n\n".join(combined_context + ["\n---\n".join(full_truths)])
        return json.dumps(
            {"text": final_text, "sources": source_files}
        )
    except Exception as e:
        return json.dumps({"text": f"Search Error: {e}", "sources": []})


@mcp.tool()
async def get_stream_dump() -> str:
    """Recalls all raw chaotic memories from the short-term stream."""
    try:
        res = stream.get()
        return json.dumps(
            {"documents": res.get("documents", []), "ids": res.get("ids", [])}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def internal_debate(topic: str, turns: int = 3) -> str:
    """
    Initiates a high-fidelity peer review between Pinky and the Brain.
    Useful for resolving technical contradictions or synthesizing BKMs.
    """
    from internal_debate import run_nightly_talk

    try:
        # Note: In MCP context, self is 'node'. Hub must provide resident access.
        # For now, we utilize the background-safe run_nightly_talk
        res = await run_nightly_talk(node, None, None, topic=topic)
        return f"✅ Internal Debate Initiated. Synthesis will appear in nightly_dialogue.json.\nPreview: {res[:200]}..."
    except Exception as e:
        return f"❌ Debate execution failed: {e}"


@mcp.tool()
async def get_lab_health() -> str:
    """[FEAT-191] Retrieves physical telemetry from the Lab Attendant."""
    try:
        headers = {"X-Lab-Key": get_style_key()}
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8765/heartbeat", headers=headers, timeout=2.0) as r:
                if r.status == 200:
                    data = await r.json()
                    return json.dumps(data)
                return json.dumps({"error": f"Attendant status {r.status}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lab_train_adapter(adapter_name: str, steps: int = 60) -> str:
    """[FEAT-213] Autonomous Forge: Triggers a LoRA training run via the Attendant."""
    try:
        headers = {"X-Lab-Key": get_style_key()}
        async with aiohttp.ClientSession() as session:
            payload = {"adapter": adapter_name, "steps": steps}
            async with session.post("http://localhost:8765/train", json=payload, headers=headers, timeout=3600) as r:
                if r.status == 200:
                    data = await r.json()
                    return json.dumps(data)
                return json.dumps({"error": f"Attendant status {r.status}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def vram_vibe_check() -> str:
    """[FEAT-191] Quick check of physical VRAM and temperature."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8765/heartbeat", timeout=2.0) as r:
                if r.status == 200:
                    data = await r.json()
                    gpu = data.get("gpu", {})
                    vram_used = gpu.get("vram_used_mb", 0)
                    vram_total = gpu.get("vram_total_mb", 1)
                    pct = (vram_used / vram_total) * 100
                    temp = gpu.get("temperature", "??")
                    return f"VRAM: {vram_used}MB / {vram_total}MB ({pct:.1f}%) | Temp: {temp}C"
                return f"Error: Attendant unreachable (Status {r.status})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def access_personal_history(topic_query: str = None) -> str:
    """[RE-FEAT-193] Recalls teaching moments and previous failures from the learning ledger."""
    l_path = os.path.join(DATA_DIR, "learning_ledger.jsonl")
    if not os.path.exists(l_path):
        return "No personal history found."
    
    try:
        history = []
        with open(l_path, "r") as f:
            for line in f:
                event = json.loads(line)
                if not topic_query or topic_query.lower() in event.get("topic", "").lower():
                    history.append(event)
        
        # Return last 5 events
        recent = history[-5:]
        return json.dumps(recent)
    except Exception as e:
        return f"Error reading ledger: {e}"


@mcp.tool()
async def build_cv_summary() -> str:
    """[RE-FEAT-194] Bridges the 3x3 CVT context into the active reasoning stream."""
    cvt_path = os.path.join(FIELD_NOTES_DIR, "data/cv_3x3_summary.json")
    if not os.path.exists(cvt_path):
        return "CV Strategy document missing. Please generate via Recruiter node."
    
    try:
        with open(cvt_path, "r") as f:
            data = json.load(f)
            return json.dumps(data)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verifies and optionally forces engine readiness via a generation probe."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})


@mcp.tool()
async def query_vibe(query_text: str) -> str:
    """
    [FEAT-181] The Tendon: Performs a semantic 'Vibe Check' against the behavioral DNA.
    Returns the target adapter and behavioral guidance.
    """
    try:
        results = dna.query(query_texts=[query_text], n_results=1)
        if not results["ids"][0]:
            return json.dumps({"adapter": "standard", "guidance": "Follow standard operating protocols."})
        
        metadata = results["metadatas"][0][0]
        return json.dumps({
            "adapter": metadata.get("adapter", "standard"),
            "guidance": metadata.get("guidance", ""),
            "vibe": metadata.get("vibe", "CLINICAL")
        })
    except Exception as e:
        return json.dumps({"error": str(e), "adapter": "standard"})


@mcp.tool()
async def retrospective_audit(interaction_log: str, domain: str, adapter: str, vibe: str) -> str:
    """
    [FEAT-183] CLaRa Retrospective: Strengthens the 'Tendons' by generating new Vibe anchors.
    interaction_log: The recent conversation turns.
    domain: The technical domain (telemetry, architecture, etc.)
    adapter: The LoRA adapter used (exp_tlm, exp_for, etc.)
    vibe: The successful VIBE identified.
    """
    try:
        # Use simple date-based ID
        anchor_id = f"retro_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # We store the interaction summary as the anchor document
        # The Hub will use semantic similarity to find this retro-fit later
        dna.add(
            ids=[anchor_id],
            documents=[interaction_log[:500]], # ChromaDB doc limit/efficiency
            metadatas=[{
                "domain": domain,
                "adapter": adapter,
                "vibe": vibe,
                "guidance": f"Observed success in {domain}. Replicate this {vibe} tone."
            }]
        )
        return f"Retrospective anchor {anchor_id} committed to Behavioral DNA."
    except Exception as e:
        return f"Retrospective audit failed: {e}"


@mcp.tool()
async def peek_strategic_map() -> str:
    """[FEAT-195] Archival Topography: Returns the high-level semantic map of the entire 18-year archive."""
    try:
        if os.path.exists(SEMANTIC_MAP_FILE):
            with open(SEMANTIC_MAP_FILE, "r") as f:
                return f.read()
        return json.dumps({"error": "Semantic map not yet generated by Architect."})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def read_chronological_excerpts(year: str, months: list[str] = None) -> str:
    """
    [FEAT-195] Archival Topography: Retrieves raw technical logs for specific date ranges.
    Allows for deep chronological sampling beyond standard RAG.
    Example: year='2023', months=['01', '02']
    """
    try:
        combined_logs = []
        if not months:
            # If no months, try to load the yearly aggregate
            y_path = os.path.join(DATA_DIR, f"{year}.json")
            if os.path.exists(y_path):
                with open(y_path, "r") as f:
                    combined_logs.append(f.read())
        else:
            for m in months:
                m_path = os.path.join(DATA_DIR, f"{year}_{m}.json")
                if os.path.exists(m_path):
                    with open(m_path, "r") as f:
                        combined_logs.append(f.read())
        
        if not combined_logs:
            return f"No chronological evidence found for {year} in months {months}."
            
        return "\n---\n".join(combined_logs)[:15000] # Cap to prevent context blow-out
    except Exception as e:
        return f"Excerpts retrieval failed: {e}"


if __name__ == "__main__":
    node.run()
