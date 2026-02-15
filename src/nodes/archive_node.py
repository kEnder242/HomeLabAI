import os
import json
import logging
import datetime
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DRAFTS_DIR = os.path.join(WORKSPACE_DIR, "docs/drafts")
SEARCH_INDEX_PATH = os.path.join(WORKSPACE_DIR, "field_notes/search_index.json")

# Ensure paths exist
os.makedirs(DRAFTS_DIR, exist_ok=True)

# Initialize MCP
mcp = FastMCP("ArchiveNode")

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("archive_node")

# Global Stream (Mock or placeholder for now)
class MemoryStream:
    def get(self):
        return []

stream = MemoryStream()

# --- Semantic Store (Placeholder) ---
class SemanticStore:
    def query(self, query_texts, n_results=3):
        return {"documents": [[]]}

wisdom = SemanticStore()

@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """RLM Research Pattern: Follows technical breadcrumbs in Field Notes."""
    try:
        if not os.path.exists(SEARCH_INDEX_PATH):
            return "Error: Search index missing."
        with open(SEARCH_INDEX_PATH, 'r') as f:
            index = json.load(f)
        matches = []
        for slug, tags in index.items():
            if keyword.lower() in slug.lower() or any(
                keyword.lower() in t.lower() for t in tags
            ):
                matches.append(slug)
        if not matches:
            return f"No notes found relating to '{keyword}'."
        return f"Related technical breadcrumbs: {', '.join(matches[:10])}"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def build_cv_summary(year: str) -> str:
    """The High-Fidelity Distiller: Retrieves focal and artifact context for a year.
    Used to build 3x3 CVT resume summaries."""
    context = []
    # 1. Strategic Pillars from Wisdom
    try:
        res = wisdom.query(
            query_texts=[f"{year} performance review focal strategic goals"],
            n_results=3
        )
        if res['documents'][0]:
            context.append(f"STRATEGIC PILLARS ({year}):")
            context.extend(res['documents'][0])
    except Exception:
        pass

    # 2. Technical Artifacts from Field Notes
    path = os.path.join(WORKSPACE_DIR, f"field_notes/data/{year}.json")
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                if data:
                    context.append(f"\nTECHNICAL EVIDENCE ({year}):")
                    for item in data[:8]:
                        summary = item.get('summary')
                        gem = item.get('technical_gem', 'No gem')
                        context.append(f"- {summary} ({gem})")
        except Exception:
            pass
    return "\n".join(context) if context else f"No strategic context found for {year}."

@mcp.tool()
def access_personal_history(keyword: str) -> str:
    """Deep Grounding: Access 18 years of technical truth."""
    return peek_related_notes(keyword)

@mcp.tool()
def write_draft(filename: str, content: str) -> str:
    """Stage a new technical artifact or BKM in the drafts folder."""
    path = os.path.join(DRAFTS_DIR, filename)
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Draft saved to {filename}."
    except Exception as e:
        return f"Error saving draft: {e}"

@mcp.tool()
def patch_file(filename: str, diff: str, mode: str = "diff") -> str:
    """Apply granular updates via Scalpel v3.0.
    mode: 'diff' (Unified Diff) or 'block' (Search/Replace)."""
    path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(path):
        return f"Error: Workspace file '{filename}' not found."
    try:
        import subprocess
        scalpel_path = "/home/jallred/Dev_Lab/HomeLabAI/src/debug/scalpel.py"
        python_path = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3"
        res = subprocess.run(
            [python_path, scalpel_path, path, mode, diff],
            capture_output=True, text=True
        )
        return res.stdout if res.returncode == 0 else f"Scalpel Error:\n{res.stdout}"
    except Exception as e:
        return f"Error during patching: {e}"

@mcp.tool()
def create_event_for_learning(topic: str, context: str, successful: bool) -> str:
    """The Pedagogue's Ledger: Logs teaching moments or failures."""
    try:
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "topic": topic,
            "context": context,
            "successful": successful
        }
        l_path = os.path.join(WORKSPACE_DIR, "field_notes/data/learning_ledger.jsonl")
        with open(l_path, 'a') as f:
            f.write(json.dumps(event) + "\n")
        return f"Event logged to Ledger: {topic} (Success: {successful})"
    except Exception as e:
        return f"Error logging event: {e}"

@mcp.tool()
def read_document(filename: str) -> str:
    """Reads content from workspace or drafts."""
    for folder in [WORKSPACE_DIR, DRAFTS_DIR]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
    return f"Error: File '{filename}' not found."

@mcp.tool()
def get_stream_dump() -> str:
    """Retrieve full raw short-term memory stream."""
    try:
        data = stream.get()
        return json.dumps(data)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_history(limit: int = 10) -> str:
    """Retrieve recent interaction history."""
    return "History retrieval not implemented."

if __name__ == "__main__":
    mcp.run()
