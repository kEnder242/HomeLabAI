import json
import os
import glob
import chromadb
from chromadb.utils import embedding_functions
import logging

# Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_WISDOM = "long_term_wisdom"

logging.basicConfig(level=logging.INFO)

def main():
    print("--- Bridging 'Slow Burn' Artifacts to RAG ---")
    
    # 1. Init Chroma
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    wisdom = chroma_client.get_or_create_collection(name=COLLECTION_WISDOM, embedding_function=ef)

    # 2. Find Artifacts
    files = glob.glob(os.path.join(FIELD_NOTES_DATA, "*.json"))
    ignore_files = ["themes.json", "status.json", "queue.json", "state.json", "search_index.json", "pager_activity.json", "file_manifest.json"]
    
    total_added = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        if fname in ignore_files: continue
        
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
            
            if not isinstance(data, list): continue
            
            for event in data:
                # Distill event into a searchable string
                summary = event.get('summary', '')
                gem = event.get('technical_gem', '')
                date = event.get('date', 'Unknown')
                content = f"[{date}] {summary}. Technical Details: {gem}"
                
                # Check for existing (simple ID check based on summary/date hash)
                import hashlib
                event_id = f"artifact_{hashlib.md5(content.encode()).hexdigest()}"
                
                # Check if ID exists (Chroma doesn't have a simple 'exists' but we can try/catch or query)
                existing = wisdom.get(ids=[event_id])
                if not existing['ids']:
                    wisdom.add(
                        documents=[content],
                        metadatas=[{"source": fname, "date": date, "type": "artifact"}],
                        ids=[event_id]
                    )
                    total_added += 1
                    
        except Exception as e:
            print(f"Error processing {fname}: {e}")

    print(f"Success: Synced {total_added} new technical artifacts into Wisdom collection.")

if __name__ == "__main__":
    main()
