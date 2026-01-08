from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.utils import embedding_functions
import os
import logging
import datetime

# Configuration
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_NAME = "personal_knowledge"

# Initialize MCP
mcp = FastMCP("The Archives")

# Database Init
logging.info(f"📚 Archives: Opening ChromaDB at {DB_PATH}")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
collection = chroma_client.get_collection(
    name=COLLECTION_NAME, embedding_function=ef
)

@mcp.tool()
def get_context(query: str, n_results: int = 2) -> str:
    """
    Search the Archives for relevant information.
    """
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        if results and results['documents']:
            docs = results['documents'][0]
            context = "\n".join(docs)
            return context
    except Exception as e:
        return f"Archive Error: {e}"
    return ""

@mcp.tool()
def save_interaction(user_query: str, response: str) -> str:
    """
    Save a conversation turn to the Archives.
    """
    timestamp = datetime.datetime.now().isoformat()
    doc_text = f"User: {user_query}\nResponse: {response}"
    
    # TODO: Integration with CLaRa for summarization before saving
    
    collection.add(
        documents=[doc_text],
        metadatas=[{"timestamp": timestamp, "type": "conversation"}],
        ids=[f"turn_{timestamp}"]
    )
    return "Saved."

if __name__ == "__main__":
    mcp.run()
