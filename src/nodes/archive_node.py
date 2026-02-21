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

@mcp.tool()
async def write_draft(filename: str, content: str) -> str:
    """Stage a new technical artifact or BKM."""
    path = os.path.join(DRAFTS_DIR, filename)
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Draft saved to {filename}."
    except Exception as e:
        return f"Error saving draft: {e}"

@mcp.tool()
async def prune_insights(start_date: str, end_date: str, pattern: str, field: str = "summary") -> str:
    """[FEAT-073] Surgically redacts or trims data from note summaries within a date range."""
    import re
    try:
        s_date = datetime.datetime.strptime(start_date, "%Y-%m")
        e_date = datetime.datetime.strptime(end_date, "%Y-%m")
        
        modified_files = []
        
        # Iterate through months in range
        curr = s_date
        while curr <= e_date:
            fname = f"{curr.year}_{curr.month:02d}.json"
            fpath = os.path.join(DATA_DIR, fname)
            
            if os.path.exists(fpath):
                with open(fpath, 'r') as f:
                    data = json.load(f)
                
                changed = False
                for entry in data:
                    if field in entry and isinstance(entry[field], str):
                        original = entry[field]
                        # Trim based on regex pattern
                        # e.g. r'\b[A-Z][a-z]+\b' for names, or specific strings
                        entry[field] = re.sub(pattern, "[REDACTED]", original)
                        if entry[field] != original:
                            changed = True
                
                if changed:
                    with open(fpath, 'w') as f:
                        json.dump(data, f, indent=2)
                    modified_files.append(fname)
            
            # Next month
            if curr.month == 12:
                curr = datetime.datetime(curr.year + 1, 1, 1)
            else:
                curr = datetime.datetime(curr.year, curr.month + 1, 1)
                
        return f"Pruning complete. Modified {len(modified_files)} files: {', '.join(modified_files)}"
    except Exception as e:
        return f"Pruning failed: {e}"

if __name__ == "__main__":
    node.run()
