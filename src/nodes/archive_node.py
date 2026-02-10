from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions
import os
import sys
import logging
import datetime
import numpy as np
import json
from tqdm import tqdm

# Force logging to stderr to avoid corrupting MCP stdout
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

# Disable TQDM to protect MCP stdout
os.environ["TQDM_DISABLE"] = "1" 

# Configuration
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
# Tiered Memory Collections
COLLECTION_STREAM = "short_term_stream" # The Pile (Raw logs)
COLLECTION_WISDOM = "long_term_wisdom" # The Library (Consolidated)
COLLECTION_CACHE = "semantic_cache" # The Vault (Expensive Brain Responses)

# Initialize MCP
mcp = FastMCP("The Archives")

# Database Init
logging.info(f"📚 Archives: Opening ChromaDB at {DB_PATH}")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Initialize Collections with Robust Fallback
def get_safe_collection(name):
    try:
        return chroma_client.get_or_create_collection(name=name, embedding_function=ef)
    except ValueError:
        logging.warning(f"⚠️ ChromaDB Embedding Conflict for '{name}'. Using persisted function.")
        return chroma_client.get_or_create_collection(name=name)

stream = get_safe_collection(COLLECTION_STREAM)
wisdom = get_safe_collection(COLLECTION_WISDOM)
cache = get_safe_collection(COLLECTION_CACHE)

# Semantic Anchors for Routing
BRAIN_ANCHORS = [
    "Calculate pi to 10 decimal places",
    "Write python code for a websocket server",
    "Analyze the following data and find trends",
    "Solve this math problem",
    "Give me a technical summary",
    "How does a nuclear reactor work?",
    "Research the history of Rome",
    "What did I do in 2019?"
]

PINKY_ANCHORS = [
    "Hello there!",
    "Tell me a joke about mice",
    "How are you doing today?",
    "Narf!",
    "Let's just chat for a bit"
]

# Pre-compute Anchor Embeddings
logging.info("🧠 Pre-computing Semantic Anchors...")
brain_vectors = np.array(ef(BRAIN_ANCHORS))
pinky_vectors = np.array(ef(PINKY_ANCHORS))

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

# Paths for Field Notes integration
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
SEARCH_INDEX = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/search_index.json")

@mcp.tool()
def get_lab_status() -> str:
    """
    Checks the status of Lab services and system health.
    Verifies reachability of Grafana, the Pager, and the Public Airlock.
    """
    import requests
    import subprocess
    
    status = []
    
    # 1. System Load & Thermal
    try:
        cmd = ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            temp, gpu = res.stdout.strip().split(", ")
            status.append(f"GPU: {temp}C / {gpu}% Load")
    except: pass

    # 2. Service Reachability (Internal)
    services = {
        "Grafana": "http://localhost:3000",
        "Prometheus": "http://localhost:9090",
        "Airlock": "https://www.jason-lab.dev"
    }
    
    for name, url in services.items():
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                status.append(f"{name}: ONLINE")
            else:
                status.append(f"{name}: ERROR ({r.status_code})")
        except:
            status.append(f"{name}: OFFLINE")

    return " | ".join(status)

@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """
    RLM (Recursive LMs) Tool: Allows Pinky to 'peek' into the Field Notes artifacts.
    Searches the search_index for a keyword and returns a distilled summary of related events.
    Use this to find technical 'ground truth' or BKMs from the 18-year archive.
    """
    if not os.path.exists(SEARCH_INDEX):
        return "Error: Search Index not found."
    
    try:
        with open(SEARCH_INDEX, 'r') as f:
            index = json.load(f)
        
        # 1. Triage: Find IDs for the keyword
        keyword_clean = keyword.lower().strip()
        target_ids = index.get(keyword_clean, [])
        
        if not target_ids:
            # Fuzzy match attempt
            for k in index.keys():
                if keyword_clean in k:
                    target_ids = index[k]
                    break
        
        if not target_ids:
            return f"No technical artifacts found for '{keyword}'."
            
        # 2. Retrieve: Load the data files for the top 2 IDs
        results = []
        for tid in target_ids[:2]:
            file_path = os.path.join(FIELD_NOTES_DATA, f"{tid.replace('-', '_')}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as df:
                    data = json.load(df)
                    if isinstance(data, list):
                        for event in data[:3]:
                            results.append(f"[{event.get('date')}] {event.get('summary')}: {event.get('technical_gem', 'No technical gem listed.')}")
            else:
                results.append(f"Note: Artifact '{tid}' manifest found, but raw data is missing.")
                
        if not results:
            return f"Found references to {target_ids}, but data was empty or restricted."
            
        return "RESEARCH FINDINGS:\n" + "\n---\n".join(results)
        
    except Exception as e:
        return f"Error peeking at notes: {e}"

@mcp.tool()
def vram_vibe_check() -> str:
    """
    Checks the local system health (VRAM / Temperature).
    Returns a string describing the current system vibe.
    """
    try:
        import subprocess
        # Get Temperature and Utilization
        cmd = ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory", "--format=csv,noheader,nounits"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            temp, gpu, vram = res.stdout.strip().split(", ")
            return f"The vibe is... {temp}C at {gpu}% GPU load. VRAM is {vram}% full. Narf!"
        return "The vibe is... mysterious. (nvidia-smi failed)"
    except Exception as e:
        return f"Egad! I couldn't check the vibe: {e}"

@mcp.tool()
def add_routing_anchor(target: str, anchor_text: str) -> str:
    """Adds a new semantic anchor to improve the Semantic Router."""
    global brain_vectors, pinky_vectors, BRAIN_ANCHORS, PINKY_ANCHORS
    if target.upper() == "BRAIN":
        BRAIN_ANCHORS.append(anchor_text)
        brain_vectors = np.array(ef(BRAIN_ANCHORS))
        return f"Added BRAIN anchor: '{anchor_text}'"
    elif target.upper() == "PINKY":
        PINKY_ANCHORS.append(anchor_text)
        pinky_vectors = np.array(ef(PINKY_ANCHORS))
        return f"Added PINKY anchor: '{anchor_text}'"
    return "Error: target must be 'BRAIN' or 'PINKY'"

@mcp.tool()
def classify_intent(query: str) -> dict:
    """Classifies user query as 'BRAIN' or 'PINKY'."""
    query_vector = np.array(ef([query])[0])
    brain_sim = max([cosine_similarity(query_vector, bv) for bv in brain_vectors])
    pinky_sim = max([cosine_similarity(query_vector, pv) for pv in pinky_vectors])
    target = "PINKY"
    if brain_sim > pinky_sim and brain_sim > 0.4: target = "BRAIN"
    elif brain_sim > 0.6: target = "BRAIN"
    return {"target": target, "confidence": float(max(brain_sim, pinky_sim))}

@mcp.tool()
def consult_clipboard(query: str, threshold: float = 0.35, max_age_days: int = 14) -> str | None:
    """Check Semantic Cache for past Brain responses."""
    try:
        results = cache.query(query_texts=[query], n_results=1)
        if not results['documents'][0]: return None
        distance = results['distances'][0][0]
        metadata = results['metadatas'][0][0]
        if distance < threshold:
            return metadata['response']
        return None
    except: return None

@mcp.tool()
def scribble_note(query: str, response: str) -> str:
    """Cache a response."""
    try:
        timestamp = datetime.datetime.now().isoformat()
        cache.add(documents=[query], metadatas=[{"response": response, "timestamp": timestamp}], ids=[f"cache_{timestamp}"])
        return "Note scribbled."
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def clear_collection(collection_name: str) -> str:
    """Clears a collection safely."""
    try:
        chroma_client.delete_collection(name=collection_name)
        if collection_name == COLLECTION_CACHE: global cache; cache = get_safe_collection(COLLECTION_CACHE)
        elif collection_name == COLLECTION_STREAM: global stream; stream = get_safe_collection(COLLECTION_STREAM)
        elif collection_name == COLLECTION_WISDOM: global wisdom; wisdom = get_safe_collection(COLLECTION_WISDOM)
        return f"Collection '{collection_name}' cleared."
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def get_context(query: str, n_results: int = 3) -> str:
    """Search Archives prioritizing Wisdom."""
    try:
        res_wisdom = wisdom.query(query_texts=[query], n_results=n_results)
        docs = res_wisdom.get('documents', [[]])[0]
        if len(docs) < n_results:
            res_stream = stream.query(query_texts=[query], n_results=n_results - len(docs))
            docs.extend(res_stream.get('documents', [[]])[0])
        return "\n---\n".join(docs)
    except Exception as e: return f"Error: {e}"

@mcp.tool()
def save_interaction(user_query: str, response: str) -> str:
    """Save turn to stream."""
    timestamp = datetime.datetime.now().isoformat()
    doc_text = f"[{timestamp}] User: {user_query}\nPinky/Brain: {response}"
    stream.add(documents=[doc_text], metadatas=[{"timestamp": timestamp, "type": "raw_turn"}], ids=[f"turn_{timestamp}"])
    return "Stored in Stream."

@mcp.tool()
def get_stream_dump() -> str:
    """
    Returns all raw interaction logs currently in the short-term stream.
    Used by the Dream Cycle for synthesis.
    """
    try:
        data = stream.get()
        return json.dumps({"documents": data['documents'], "ids": data['ids']})
    except Exception as e:
        return json.dumps({"documents": [], "ids": [], "error": str(e)})

@mcp.tool()
def dream(summary: str, sources: list[str]) -> str:
    """
    Consolidates synthesized wisdom into long-term memory and purges raw sources.
    This is the 'Subconscious Compression' phase.
    """
    try:
        timestamp = datetime.datetime.now().isoformat()
        # 1. Store the high-density wisdom
        wisdom.add(
            documents=[summary],
            metadatas=[{"timestamp": timestamp, "type": "dream_summary", "source_count": len(sources)}],
            ids=[f"dream_{timestamp}"]
        )
        # 2. Purge the raw chaotic memories
        if sources:
            stream.delete(ids=sources)
        return f"Dreaming complete. Consolidated {len(sources)} memories into Diamond Wisdom."
    except Exception as e:
        return f"Dream failed: {e}"

if __name__ == "__main__":
    mcp.run()
