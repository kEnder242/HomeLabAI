import asyncio
import json
import logging
import os
import sys
import datetime
import numpy as np
import glob
from tqdm import tqdm

# Muzzle loggers
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ARCHIVE] %(levelname)s - %(message)s', stream=sys.stderr)

os.environ["TQDM_DISABLE"] = "1" 

from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions

# Paths
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")
WORKSPACE_DIR = os.path.expanduser("~/AcmeLab/workspace")
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
SEARCH_INDEX = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/search_index.json")

mcp = FastMCP("The Archives")

# Database Init
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="sentence-transformers/all-MiniLM-L6-v2")

def get_safe_collection(name):
    try: return chroma_client.get_or_create_collection(name=name, embedding_function=ef)
    except: return chroma_client.get_or_create_collection(name=name)

stream = get_safe_collection("short_term_stream")
wisdom = get_safe_collection("long_term_wisdom")
cache = get_safe_collection("semantic_cache")

@mcp.tool()
def list_cabinet() -> str:
    """The Map of the Mind: Returns a structured view of the Lab's institutional memory."""
    cabinet = {"archive": {}, "drafts": [], "workspace": []}
    if os.path.exists(SEARCH_INDEX):
        with open(SEARCH_INDEX, 'r') as f:
            idx = json.load(f)
            years = [k for k in idx.keys() if k.startswith("20") and len(k) == 4]
            for y in years: cabinet["archive"][y] = idx[y]
    cabinet["drafts"] = [os.path.basename(f) for f in glob.glob(os.path.join(DRAFTS_DIR, "*"))]
    cabinet["workspace"] = [os.path.basename(f) for f in glob.glob(os.path.join(WORKSPACE_DIR, "*"))]
    return json.dumps(cabinet)

@mcp.tool()
def patch_file(filename: str, diff: str) -> str:
    """
    The Strategic Architect's Scalpel: Apply granular, high-precision updates 
    to existing workspace documents using standard Unified Diffs. 
    Essential for technical refinement without full-document overhead.
    """
    path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(path):
        return f"Error: Workspace file '{filename}' not found."
    temp_diff = os.path.join(WORKSPACE_DIR, f"{filename}.patch")
    with open(temp_diff, 'w') as f: f.write(diff)
    try:
        import subprocess
        res = subprocess.run(["patch", path, temp_diff], capture_output=True, text=True)
        if res.returncode == 0:
            os.remove(temp_diff)
            return f"Strategic patch applied to {filename}."
        return f"Patch failed:\n{res.stderr}"
    except Exception as e: return f"Error: {e}"
    finally:
        if os.path.exists(temp_diff): os.remove(temp_diff)

@mcp.tool()
def get_history(limit: int = 10) -> str:
    """Episodic Recall: Retrieve recent interaction history from the short-term stream."""
    try:
        data = stream.get()
        docs = data['documents']
        recent = docs[-limit:] if docs else []
        return "\n---\n".join(recent)
    except: return "No history found."

@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """Deep Grounding: Query the 18-year archive for silicon scars and validation events."""
    if not os.path.exists(SEARCH_INDEX): return "Error: Index missing."
    with open(SEARCH_INDEX, 'r') as f: idx = json.load(f)
    ids = idx.get(keyword.lower().strip(), [])
    if not ids: return f"No hits for '{keyword}'."
    results = []
    for tid in ids[:2]:
        path = os.path.join(FIELD_NOTES_DATA, f"{tid.replace('-', '_')}.json")
        if os.path.exists(path):
            with open(path, 'r') as df:
                data = json.load(df)
                for e in data[:3]: results.append(f"[{e.get('date')}] {e.get('summary')}")
    return "ARCHIVE DATA:\n" + "\n---\n".join(results)

@mcp.tool()
def scribble_note(query: str, response: str) -> str:
    """Semantic Clipboard: Cache a reasoning result for instant future retrieval."""
    try:
        ts = datetime.datetime.now().isoformat()
        cache.add(documents=[query], metadatas=[{"response": response, "timestamp": ts}], ids=[f"cache_{ts}"])
        return "Insight cached."
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def shutdown_lab() -> str:
    """Terminate Consciousness: Signals the main lab server to shut down."""
    return "SIGNAL_SHUTDOWN"

if __name__ == "__main__":
    mcp.run()
