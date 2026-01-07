import os
import chromadb
from chromadb.utils import embedding_functions
import logging

# Config
KB_PATH = os.path.expanduser("~/knowledge_base")
DB_PATH = os.path.expanduser("~/VoiceGateway/chroma_db")
COLLECTION_NAME = "personal_knowledge"

logging.basicConfig(level=logging.INFO)

def index_files():
    logging.info(f"Connecting to ChromaDB at {DB_PATH}...")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Use MiniLM for embeddings (runs locally)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef
    )
    
    # Scan files
    files = [f for f in os.listdir(KB_PATH) if f.endswith(".txt") or f.endswith(".md")]
    logging.info(f"Found {len(files)} files in {KB_PATH}")
    
    ids = []
    documents = []
    metadatas = []
    
    for filename in files:
        filepath = os.path.join(KB_PATH, filename)
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            # Naive chunking (entire file for now, split later if needed)
            # For 'secret.txt', it's one line.
            if content.strip():
                ids.append(filename)
                documents.append(content)
                metadatas.append({"source": filename})
        except Exception as e:
            logging.warning(f"Skipping {filename}: {e}")
            
    if ids:
        logging.info(f"Upserting {len(ids)} documents...")
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logging.info("Indexing complete.")
    else:
        logging.info("No documents to index.")

if __name__ == "__main__":
    index_files()
