from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions
import os
import logging
import datetime

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