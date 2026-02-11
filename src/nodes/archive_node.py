import asyncio
import json
import logging
import os
import sys
import datetime
import numpy as np
import glob
from tqdm import tqdm

# Muzzle chatty loggers immediately
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)
logging.getLogger("nemo").setLevel(logging.CRITICAL) # Just in case it's here
logging.getLogger("onnxruntime").setLevel(logging.CRITICAL)

# Basic config, now that the other loggers are muzzled
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ARCHIVE] %(levelname)s - %(message)s', stream=sys.stderr)

os.environ["TQDM_DISABLE"] = "1" 

from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

# Configuration (Assuming this is already defined elsewhere or should be here)
# For the purpose of getting the file to compile, let's define them here if not imported
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
    """Returns a structured map of the filing cabinet (Archives, Drafts, Workspace)."""
    cabinet = {"archive": {}, "drafts": [], "workspace": []}
    
    # 1. Archives (from search_index)
    if os.path.exists(SEARCH_INDEX):
        with open(SEARCH_INDEX, 'r') as f:
            idx = json.load(f)
            # Find years (keys starting with 20)
            years = [k for k in idx.keys() if k.startswith("20") and len(k) == 4]
            for y in years: cabinet["archive"][y] = idx[y]
            
    # 2. Drafts
    cabinet["drafts"] = [os.path.basename(f) for f in glob.glob(os.path.join(DRAFTS_DIR, "*"))]
    
    # 3. Workspace
    cabinet["workspace"] = [os.path.basename(f) for f in glob.glob(os.path.join(WORKSPACE_DIR, "*"))]
    
    return json.dumps(cabinet)

@mcp.tool()
def read_document(filename: str) -> str:
    """Reads a file from drafts/ or workspace/."""
    for d in [WORKSPACE_DIR, DRAFTS_DIR]:
        path = os.path.join(d, filename)
        if os.path.exists(path):
            with open(path, 'r') as f: return f.read()
    return f"Error: Document '{filename}' not found."

@mcp.tool()
def get_history(limit: int = 10) -> str:
    """Retrieves the recent interaction history from the stream."""
    try:
        data = stream.get()
        docs = data['documents']
        # Return last N turns
        recent = docs[-limit:] if docs else []
        return "\n---\n".join(recent)
    except: return "No history found."

@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """Retrieves ground truth from the 18-year archive index."""
    if not os.path.exists(SEARCH_INDEX): return "Error: Index missing."
    with open(SEARCH_INDEX, 'r') as f: idx = json.load(f)
    ids = idx.get(keyword.lower().strip(), [])
    if not ids: return f"No archive hits for '{keyword}'."
    results = []
    for tid in ids[:2]:
        path = os.path.join(FIELD_NOTES_DATA, f"{tid.replace('-', '_')}.json")
        if os.path.exists(path):
            with open(path, 'r') as df:
                data = json.load(df)
                for e in data[:3]: results.append(f"[{e.get('date')}] {e.get('summary')}")
    return "ARCHIVE DATA:\n" + "\n---\n".join(results)

@mcp.tool()
def get_context(query: str, n_results: int = 3) -> str:
    """Vector search prioritize Wisdom collection."""
    res = wisdom.query(query_texts=[query], n_results=n_results)
    return "\n---\n".join(res.get('documents', [[]])[0])

@mcp.tool()
def save_interaction(user_query: str, response: str) -> str:
    """Log turn to stream."""
    ts = datetime.datetime.now().isoformat()
    text = f"[{ts}] User: {user_query}\nResponse: {response}"
    stream.add(documents=[text], metadatas=[{"ts": ts}], ids=[f"t_{ts}"])
    return "Interaction saved."

@mcp.tool()
def get_lab_status() -> str:
    import requests, subprocess
    out = []
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"], capture_output=True, text=True)
        out.append(f"GPU: {res.stdout.strip()}C")
    except: pass
    return " | ".join(out)

if __name__ == "__main__":
    mcp.run()