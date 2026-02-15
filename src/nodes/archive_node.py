import os
import json
import logging
import datetime
import glob
from nodes.loader import BicameralNode

# --- Configuration ---
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DRAFTS_DIR = os.path.join(WORKSPACE_DIR, "docs/drafts")
FIELD_NOTES_DIR = os.path.join(WORKSPACE_DIR, "field_notes")
DATA_DIR = os.path.join(FIELD_NOTES_DIR, "data")

# Ensure paths exist
os.makedirs(DRAFTS_DIR, exist_ok=True)

# Logging
logging.basicConfig(level=logging.ERROR)

ARCHIVE_SYSTEM_PROMPT = (
    "You are the Archive Node. You have access to the Filing Cabinet. "
    "Your duty is to list and read documents accurately."
)

node = BicameralNode("ArchiveNode", ARCHIVE_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def list_cabinet() -> str:
    """The Filing Cabinet: Lists all openable technical artifacts (JSON and HTML)."""
    try:
        all_items = []
        jsons = glob.glob(os.path.join(DATA_DIR, "20*.json"))
        all_items.extend([os.path.basename(f) for f in jsons])
        htmls = glob.glob(os.path.join(FIELD_NOTES_DIR, "*.html"))
        all_items.extend([os.path.basename(f) for f in htmls])
        drafts = glob.glob(os.path.join(DRAFTS_DIR, "*"))
        all_items.extend([os.path.basename(f) for f in drafts])
        return json.dumps(sorted(list(set(all_items))))
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def read_document(filename: str) -> str:
    """Reads content from workspace, drafts, or data folders."""
    search_paths = [
        os.path.join(DRAFTS_DIR, filename),
        os.path.join(DATA_DIR, filename),
        os.path.join(FIELD_NOTES_DIR, filename)
    ]
    for p in search_paths:
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, 'r') as f:
                    return f.read()
            except Exception as e:
                return f"Error reading {filename}: {e}"
    return f"Error: File '{filename}' not found."


@mcp.tool()
async def peek_related_notes(keyword: str) -> str:
    """RLM Research Pattern: Follows technical breadcrumbs."""
    index_path = os.path.join(FIELD_NOTES_DIR, "search_index.json")
    try:
        if not os.path.exists(index_path):
            return "Error: Search index missing."
        with open(index_path, 'r') as f:
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
            "successful": successful
        }
        l_path = os.path.join(DATA_DIR, "learning_ledger.jsonl")
        with open(l_path, 'a') as f:
            f.write(json.dumps(event) + "\n")
        return f"Event logged: {topic} (Success: {successful})"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    node.run()
