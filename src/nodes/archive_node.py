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
    """RLM Research Pattern: Follows technical breadcrumbs."""
    index_path = os.path.join(FIELD_NOTES_DIR, "search_index.json")
    try:
        if not os.path.exists(index_path):
            return "Error: Search index missing."
        with open(index_path, "r") as f:
            index = json.load(f)
        matches = []
        k_lower = keyword.lower()
        for key in index.keys():
            if k_lower in key.lower():
                matches.extend(index[key])
        if not matches:
            return f"No notes found relating to '{keyword}'."
        return f"Related technical breadcrumbs: {', '.join(list(set(matches))[:10])}"
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


@mcp.tool()
async def get_context(query: str, n_results: int = 3) -> str:
    """
    [FEAT-117] Multi-Stage Retrieval: Discovery -> Acquisition.
    Stage 1: ChromaDB identifies the metadata anchor.
    Stage 2: ArchiveNode retrieves the raw JSON truth from filesystem.
    """
    try:
        # [FEAT-117] Hard Year Filtering (Post-Filter)
        import re
        # Support years from 1990 to 2029
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        target_year = year_match.group(1) if year_match else None
        
        fetch_limit = n_results * 5 if target_year else n_results
        if target_year:
            logging.info(f"[ARCHIVE] Applying Hard Year Post-Filter: {target_year}")

        # Stage 1: Vector Discovery
        res = wisdom.query(query_texts=[query], n_results=fetch_limit)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]

        if not docs:
            res = stream.query(query_texts=[query], n_results=fetch_limit)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]

        if not docs:
            return json.dumps({"text": "No relevant artifacts found in neural archives.", "sources": []})

        # Stage 2: Raw Acquisition (Multi-Stage Discovery)
        full_truths = []
        source_files = []
        
        # [FEAT-126/127] Yearly Summary Injection & Grounding
        if target_year:
            summary_file = f"{target_year}.json"
            summary_path = os.path.join(DATA_DIR, summary_file)
            if os.path.exists(summary_path):
                source_files.append(summary_file)
                try:
                    with open(summary_path, 'r') as f:
                        summary_data = json.load(f)
                        # Extract the Top 3 highest-rank items for strategic context
                        high_rank = sorted([e for e in summary_data if e.get('rank', 0) >= 3], 
                                         key=lambda x: x.get('rank', 0), reverse=True)[:3]
                        for entry in high_rank:
                            full_truths.append(
                                f"[STRATEGIC SUMMARY {target_year}]: {entry.get('summary')} "
                                f"(Rank: {entry.get('rank')}, Gem: {entry.get('technical_gem', 'N/A')})"
                            )
                except Exception as e:
                    logging.error(f"[ARCHIVE] Failed to parse summary {summary_file}: {e}")

        matched_count = 0
        for i, doc in enumerate(docs):
            if matched_count >= n_results:
                break
                
            meta = metas[i] if i < len(metas) else {}
            # [FIX] Handle varied metadata keys (date vs timestamp vs source)
            ts = str(meta.get("timestamp") or meta.get("date") or meta.get("source", ""))
            
            # [STRICT-YEAR] If we have a target year, strictly reject any mismatch
            if target_year and target_year not in ts:
                continue
                
            matched_count += 1
            if ts:
                # Case 1: Full filename provided
                if ts.endswith(".json"):
                    target_file = ts
                # Case 2: Date string provided (YYYY-MM-DD)
                elif len(ts) >= 7:
                    year_month = ts[:7].replace("-", "_")
                    target_file = f"{year_month}.json"
                else:
                    target_file = None

                if target_file and os.path.exists(os.path.join(DATA_DIR, target_file)):
                    # [FEAT-117] Bridge to raw JSON truth
                    full_truths.append(
                        f"[ACQUISITION Source: {target_file}]: "
                        f"Document anchor: {doc[:100]}..."
                    )
                    if target_file not in source_files:
                        source_files.append(target_file)
                    continue

            full_truths.append(f"[DISCOVERY]: {doc}")

        # [FEAT-120] Return structured JSON for Hub transparency
        return json.dumps(
            {"text": "\n---\n".join(full_truths), "sources": source_files}
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
            async with session.get("http://localhost:9999/heartbeat", headers=headers, timeout=2.0) as r:
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
            async with session.post("http://localhost:9999/train", json=payload, headers=headers, timeout=3600) as r:
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
            async with session.get("http://localhost:9999/heartbeat", timeout=2.0) as r:
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
