import datetime
import glob
import json
import logging
import os
import sys

# Muzzle loggers
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [ARCHIVE] %(levelname)s - %(message)s',
    stream=sys.stderr
)

os.environ["TQDM_DISABLE"] = "1"

from mcp.server.fastmcp import FastMCP  # noqa: E402
import chromadb  # noqa: E402
from chromadb.utils import embedding_functions  # noqa: E402

# Paths
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")
WORKSPACE_DIR = os.path.expanduser("~/AcmeLab/workspace")
FIELD_NOTES_DATA = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data"
)
SEARCH_INDEX = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/search_index.json"
)

mcp = FastMCP("The Archives")

# Database Init
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def get_safe_collection(name):
    try:
        return chroma_client.get_or_create_collection(
            name=name, embedding_function=ef
        )
    except Exception:
        return chroma_client.get_or_create_collection(name=name)


stream = get_safe_collection("short_term_stream")
wisdom = get_safe_collection("long_term_wisdom")
cache = get_safe_collection("semantic_cache")


@mcp.tool()
def list_cabinet() -> str:
    """Structure view of the Lab's institutional memory."""
    cabinet = {"archive": {}, "drafts": [], "workspace": []}
    if os.path.exists(SEARCH_INDEX):
        with open(SEARCH_INDEX, 'r') as f:
            idx = json.load(f)
            years = [k for k in idx.keys() if k.startswith("20") and len(k) == 4]
            for y in years:
                cabinet["archive"][y] = idx[y]
    cabinet["drafts"] = [
        os.path.basename(f) for f in glob.glob(os.path.join(DRAFTS_DIR, "*"))
    ]
    cabinet["workspace"] = [
        os.path.basename(f) for f in glob.glob(os.path.join(WORKSPACE_DIR, "*"))
    ]
    return json.dumps(cabinet)


@mcp.tool()
def patch_file(filename: str, diff: str) -> str:
    """Apply granular updates using standard Unified Diffs."""
    path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(path):
        return f"Error: Workspace file '{filename}' not found."
    temp_diff = os.path.join(WORKSPACE_DIR, f"{filename}.patch")
    with open(temp_diff, 'w') as f:
        f.write(diff)
    try:
        import subprocess
        res = subprocess.run(
            ["patch", path, temp_diff], capture_output=True, text=True
        )
        if res.returncode == 0:
            os.remove(temp_diff)
            return f"Strategic patch applied to {filename}."
        return f"Patch failed:\n{res.stderr}"
    except Exception as e:
        return f"Error: {e}"
    finally:
        if os.path.exists(temp_diff):
            os.remove(temp_diff)


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
def get_history(limit: int = 10) -> str:
    """Retrieve recent interaction history."""
    try:
        data = stream.get()
        docs = data['documents']
        recent = docs[-limit:] if docs else []
        return "\n---\n".join(recent)
    except Exception:
        return "No history found."


@mcp.tool()
def peek_related_notes(keyword: str) -> str:
    """Query the 18-year archive for silicon scars."""
    if not os.path.exists(SEARCH_INDEX):
        return "Error: Index missing."
    with open(SEARCH_INDEX, 'r') as f:
        idx = json.load(f)
    ids = idx.get(keyword.lower().strip(), [])
    if not ids:
        return f"No hits for '{keyword}'."
    results = []
    for tid in ids[:2]:
        path = os.path.join(FIELD_NOTES_DATA, f"{tid.replace('-', '_')}.json")
        if os.path.exists(path):
            with open(path, 'r') as df:
                data = json.load(df)
                for e in data[:3]:
                    results.append(f"[{e.get('date')}] {e.get('summary')}")
    return "ARCHIVE DATA:\n" + "\n---\n".join(results)


@mcp.tool()
def consult_clipboard(query: str, threshold: float = 0.35) -> str:
    """Check the Semantic Cache for past Brain thoughts."""
    try:
        results = cache.query(query_texts=[query], n_results=1)
        if not results['documents'][0]:
            return "None"
        distance = results['distances'][0][0]
        metadata = results['metadatas'][0][0]
        if distance < threshold:
            return metadata['response']
        return "None"
    except Exception:
        return "None"


@mcp.tool()
def scribble_note(query: str, response: str) -> str:
    """Cache a reasoning result for instant future retrieval."""
    try:
        ts = datetime.datetime.now().isoformat()
        cache.add(
            documents=[query],
            metadatas=[{"response": response, "timestamp": ts}],
            ids=[f"cache_{ts}"]
        )
        return "Insight cached."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_current_time() -> str:
    """Precision Temporal Sync: Returns current system time and date."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y %I:%M %p")


@mcp.tool()
def shutdown_lab() -> str:
    """Signals the main lab server to shut down."""
    return "SIGNAL_SHUTDOWN"


if __name__ == "__main__":
    mcp.run()
