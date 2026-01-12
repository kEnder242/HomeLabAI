from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions
import os
import logging
import datetime
import numpy as np

# Configuration
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
# Tiered Memory Collections
COLLECTION_STREAM = "short_term_stream" # The Pile (Raw logs)
COLLECTION_WISDOM = "long_term_wisdom" # The Library (Consolidated)

# Initialize MCP
mcp = FastMCP("The Archives")

# Database Init
logging.info(f"📚 Archives: Opening ChromaDB at {DB_PATH}")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Semantic Anchors for Routing
BRAIN_ANCHORS = [
    "Calculate pi to 10 decimal places",
    "Write python code for a websocket server",
    "Analyze the following data and find trends",
    "Perform complex reasoning about thermodynamics",
    "Wake up the Brain",
    "What are the hard facts about climate change?",
    "Solve this math problem",
    "Explain the theory of relativity",
    "What is the capital of France?",
    "Who won the world cup in 2022?",
    "Tell me about quantum physics",
    "Give me a technical summary",
    "How does a nuclear reactor work?",
    "Research the history of Rome",
    "Compare these two technologies"
]

PINKY_ANCHORS = [
    "Hello there!",
    "Tell me a joke about mice",
    "How are you doing today?",
    "Good morning Pinky",
    "What do you think about the vibe?",
    "Narf!",
    "Let's just chat for a bit",
    "What's your favorite non-sequitur?",
    "Hi!",
    "How's life?",
    "Just wanted to say hi",
    "Zort!",
    "Poit!",
    "Egad!"
]

# Pre-compute Anchor Embeddings
logging.info("🧠 Pre-computing Semantic Anchors...")
brain_vectors = np.array(ef(BRAIN_ANCHORS))
pinky_vectors = np.array(ef(PINKY_ANCHORS))

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

@mcp.tool()
def classify_intent(query: str) -> dict:
    """
    Classifies the user query as 'BRAIN' or 'PINKY' based on semantic proximity to anchors.
    """
    query_vector = np.array(ef([query])[0])
    
    # Calculate max similarity to each set of anchors
    brain_sim = max([cosine_similarity(query_vector, bv) for bv in brain_vectors])
    pinky_sim = max([cosine_similarity(query_vector, pv) for pv in pinky_vectors])
    
    # Decision Logic
    # We want a bias towards Pinky for chat, but Brain for anything specific.
    threshold = 0.4 # Lowered to be more sensitive to Brain tasks
    
    target = "PINKY"
    if brain_sim > pinky_sim and brain_sim > threshold:
        target = "BRAIN"
    elif brain_sim > 0.6: # High enough confidence regardless of Pinky score
        target = "BRAIN"
        
    return {
        "target": target,
        "brain_similarity": float(brain_sim),
        "pinky_similarity": float(pinky_sim),
        "confidence": float(max(brain_sim, pinky_sim))
    }

# Initialize Collections
stream = chroma_client.get_or_create_collection(name=COLLECTION_STREAM, embedding_function=ef)
wisdom = chroma_client.get_or_create_collection(name=COLLECTION_WISDOM, embedding_function=ef)

@mcp.tool()
def get_context(query: str, n_results: int = 3) -> str:
    """
    Search the Archives for relevant information.
    Prioritizes Wisdom (Long-term) then checks the Stream (Short-term).
    """
    try:
        # 1. Check Wisdom first
        res_wisdom = wisdom.query(query_texts=[query], n_results=n_results)
        docs = res_wisdom.get('documents', [[]])[0]
        
        # 2. Augment with recent stream if needed
        if len(docs) < n_results:
            res_stream = stream.query(query_texts=[query], n_results=n_results - len(docs))
            docs.extend(res_stream.get('documents', [[]])[0])
            
        return "\n---\n".join(docs)
    except Exception as e:
        return f"Archive Search Error: {e}"

@mcp.tool()
def get_stream_dump() -> dict:
    """
    Retrieve all raw logs from the short-term stream for processing.
    Returns a dict with 'documents' and 'ids'.
    """
    try:
        results = stream.get()
        return {
            "documents": results.get('documents', []),
            "ids": results.get('ids', [])
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def save_interaction(user_query: str, response: str) -> str:
    """
    Save a raw conversation turn to the Short-Term Stream.
    """
    timestamp = datetime.datetime.now().isoformat()
    doc_text = f"[{timestamp}] User: {user_query}\nPinky/Brain: {response}"
    
    stream.add(
        documents=[doc_text],
        metadatas=[{"timestamp": timestamp, "type": "raw_turn"}],
        ids=[f"turn_{timestamp}"]
    )
    return "Stored in Stream."

@mcp.tool()
def dream(summary: str, sources: list[str]) -> str:
    """
    The Brain uses this to consolidate Stream logs into Wisdom.
    Input: A high-level narrative summary and the list of raw IDs processed.
    """
    timestamp = datetime.datetime.now().isoformat()
    
    # 1. Add to Wisdom
    wisdom.add(
        documents=[summary],
        metadatas=[{"timestamp": timestamp, "type": "insight", "consolidated_from": str(sources)}],
        ids=[f"wisdom_{timestamp}"]
    )
    
    # 2. Cleanup Stream (Delete the old raw logs that were summarized)
    if sources:
        try:
            stream.delete(ids=sources)
        except: pass
        
    return f"Consolidated {len(sources)} logs into Wisdom."

if __name__ == "__main__":
    mcp.run()