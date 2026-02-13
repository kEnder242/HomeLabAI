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
def get_cv_context(year: str) -> str:
    """
    Retrieves both strategic (Focal) and technical (Artifact) context for a specific year.
    Used to build high-density 3x3 CVT resume summaries.
    """
    context = []
    
    # 1. Get Strategic 'Focal' Insights from Wisdom
    try:
        res_strat = wisdom.query(query_texts=[f"{year} performance review focal insights"], n_results=3)
        context.append("STRATEGIC PILLARS (Review Data):")
        context.extend(res_strat.get('documents', [[]])[0])
    except: pass

    # 2. Get Technical Artifacts for that year
    file_path = os.path.join(FIELD_NOTES_DATA, f"{year}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                data.sort(key=lambda x: x.get('rank', 2), reverse=True)
                context.append(f"\nTECHNICAL ARTIFACTS ({year}):")
                for event in data[:10]:
                    context.append(f"- [{event.get('date')}] {event.get('summary')}: {event.get('technical_gem', '')}")
        except: pass
    
    return "\n".join(context)

@mcp.tool()
def prune_drafts() -> str:
    """Clears all files in the drafts/ directory."""
    files = glob.glob(os.path.join(DRAFTS_DIR, "*"))
    count = 0
    for f in files:
        try:
            os.remove(f)
            count += 1
        except: pass
    return f"Housekeeping complete. Pruned {count} drafts. Narf!"

@mcp.tool()
def consult_clipboard(query: str, threshold: float = 0.35) -> str:
    """Check Semantic Cache for past Brain responses. Returns response text or 'None'."""
    try:
        results = cache.query(query_texts=[query], n_results=1)
        if not results['documents'][0]: return "None"
        distance = results['distances'][0][0]
        metadata = results['metadatas'][0][0]
        if distance < threshold:
            return metadata['response']
        return "None"
    except: return "None"

@mcp.tool()
def scribble_note(query: str, response: str) -> str:
    """Cache a response in the semantic clipboard."""
    try:
        ts = datetime.datetime.now().isoformat()
        cache.add(documents=[query], metadatas=[{"response": response, "timestamp": ts}], ids=[f"cache_{ts}"])
        return "Note scribbled."
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def dream(summary: str, sources: list[str]) -> str:
    """Consolidates synthesized interaction logs into long-term wisdom."""
    try:
        ts = datetime.datetime.now().isoformat()
        wisdom.add(
            documents=[summary],
            metadatas=[{"timestamp": ts, "type": "dream_summary", "source_count": len(sources)}],
            ids=[f"dream_{ts}"]
        )
        if sources: stream.delete(ids=sources)
        return f"Dreaming complete. Consolidated {len(sources)} memories."
    except Exception as e: return f"Dream failed: {e}"

@mcp.tool()
def get_recent_dream() -> str:
    """Retrieves the most recent synthesized dream summary."""
    try:
        res = wisdom.get(where={"type": "dream_summary"})
        if not res['documents']: return "No recent dreams found."
        
        items = []
        for i in range(len(res['documents'])):
            items.append({"doc": res['documents'][i], "meta": res['metadatas'][i]})
        items.sort(key=lambda x: x['meta'].get('timestamp', ''), reverse=True)
        latest = items[0]
        return f"[DREAM FROM {latest['meta']['timestamp']}]:\n{latest['doc']}"
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def generate_bkm(topic: str, category: str = "validation") -> str:
    """Gathers context for synthesizing a master BKM document."""
    try:
        res = wisdom.query(query_texts=[f"Technical details and scars related to {topic}"], n_results=10)
        docs = res.get('documents', [[]])[0]
        context = "\n---\n".join(docs)
    except: context = "No historical data found."
    return json.dumps({"topic": topic, "category": category, "context": context})

@mcp.tool()
def get_lab_status() -> str:
    import requests, subprocess
    out = []
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"], capture_output=True, text=True)
        out.append(f"GPU: {res.stdout.strip()}C")
    except: pass
    return " | ".join(out)

@mcp.tool()
def patch_file(filename: str, diff: str) -> str:
    """
    Applies a Unified Diff to a file in the workspace/.
    This allows for granular updates without overwriting the whole file.
    diff: The diff content in standard unified format.
    """
    path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(path):
        return f"Error: Workspace file '{filename}' not found. Create it first with 'write_document'."
    
    # Write diff to a temporary file
    temp_diff = os.path.join(WORKSPACE_DIR, f"{filename}.patch")
    with open(temp_diff, 'w') as f:
        f.write(diff)
    
    try:
        # Use system patch utility
        import subprocess
        res = subprocess.run(["patch", path, temp_diff], capture_output=True, text=True)
        if res.returncode == 0:
            os.remove(temp_diff)
            return f"Patch applied successfully to {filename}."
        else:
            return f"Patch failed for {filename}:\n{res.stderr}"
    except Exception as e:
        return f"Error applying patch: {e}"
    finally:
        if os.path.exists(temp_diff): os.remove(temp_diff)

@mcp.tool()
def shutdown_lab() -> str:
    """Signals the main lab server to shut down."""
    # We return a specific string that acme_lab.py will recognize
    return "SIGNAL_SHUTDOWN"

if __name__ == "__main__":
    mcp.run()