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


@mcp.tool()
def list_cabinet() -> str:
    """The Filing Cabinet: Lists all technical artifacts."""
    try:
        if not os.path.exists(SEARCH_INDEX_PATH):
            return json.dumps([])
        with open(SEARCH_INDEX_PATH, 'r') as f:
            index = json.load(f)
        return json.dumps(list(index.keys()))
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """RLM Research Pattern: Follows technical breadcrumbs."""
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
    """The High-Fidelity Distiller: Retrieves focal and artifact context."""
    return f"CV context for {year} retrieval logic (Stub)."


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
def read_document(filename: str) -> str:
    """Reads content from workspace or drafts."""
    for folder in [WORKSPACE_DIR, DRAFTS_DIR]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
    return f"Error: File '{filename}' not found."


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


if __name__ == "__main__":
    mcp.run()
