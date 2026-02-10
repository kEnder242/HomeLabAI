import json
import os
import glob
import chromadb
from chromadb.utils import embedding_functions
import logging
import hashlib

# Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
PORTFOLIO_ROOT = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_WISDOM = "long_term_wisdom"

logging.basicConfig(level=logging.INFO)

def main():
    print("--- Bridging 'Slow Burn' Artifacts & Strategic Stories to RAG ---")
    
    # 1. Init Chroma
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # Handle collection creation with conflict safety
    try:
        wisdom = chroma_client.get_or_create_collection(name=COLLECTION_WISDOM, embedding_function=ef)
    except ValueError:
        wisdom = chroma_client.get_or_create_collection(name=COLLECTION_WISDOM)

    # 2. Sync Technical Artifacts (Logs)
    json_files = glob.glob(os.path.join(FIELD_NOTES_DATA, "*.json"))
    ignore_files = ["themes.json", "status.json", "queue.json", "state.json", "search_index.json", "pager_activity.json", "file_manifest.json"]
    
    total_added = 0
    for fpath in json_files:
        fname = os.path.basename(fpath)
        if fname in ignore_files: continue
        
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
            if not isinstance(data, list): continue
            
            for event in data:
                summary = event.get('summary', '')
                gem = event.get('technical_gem', 'No gem.')
                date = event.get('date', 'Unknown')
                content = f"[{date}] TECHNICAL EVENT: {summary}. Gem: {gem}"
                
                event_id = f"artifact_{hashlib.md5(content.encode()).hexdigest()}"
                
                if not wisdom.get(ids=[event_id])['ids']:
                    wisdom.add(
                        documents=[content],
                        metadatas=[{"source": fname, "date": date, "type": "artifact"}],
                        ids=[event_id]
                    )
                    total_added += 1
        except Exception as e:
            print(f"Error processing {fname}: {e}")

    # 3. Sync Strategic Themes
    theme_path = os.path.join(FIELD_NOTES_DATA, "themes.json")
    if os.path.exists(theme_path):
        try:
            with open(theme_path, 'r') as f:
                themes = json.load(f)
            for year, data in themes.items():
                theme_text = data.get('strategic_theme', '')
                if theme_text:
                    content = f"[{year} STRATEGIC THEME]: {theme_text}"
                    theme_id = f"theme_{year}"
                    if not wisdom.get(ids=[theme_id])['ids']:
                        wisdom.add(
                            documents=[content],
                            metadatas=[{"source": "themes.json", "year": year, "type": "strategy"}],
                            ids=[theme_id]
                        )
                        total_added += 1
        except Exception as e:
            print(f"Error processing themes: {e}")

    # 4. Sync Strategic Documents (The 'Keep' equivalents in the FS)
    strat_docs = [
        "DEV_LAB_STRATEGY.md",
        "WWW_STRATEGY.md",
        "FIELD_NOTES_ARCHITECTURE.md",
        "RESEARCH_SYNTHESIS.md"
    ]
    for doc in strat_docs:
        doc_path = os.path.join(PORTFOLIO_ROOT, doc)
        if os.path.exists(doc_path):
            try:
                with open(doc_path, 'r') as f:
                    content = f.read()
                # Chunk large strategy docs by section
                sections = content.split('##')
                for i, section in enumerate(sections):
                    if not section.strip(): continue
                    chunk_content = f"[STRATEGY DOC: {doc}] {section.strip()}"
                    chunk_id = f"strat_{doc}_{i}"
                    if not wisdom.get(ids=[chunk_id])['ids']:
                        wisdom.add(
                            documents=[chunk_content],
                            metadatas=[{"source": doc, "type": "strategy_doc"}],
                            ids=[chunk_id]
                        )
                        total_added += 1
            except Exception as e:
                print(f"Error processing strat doc {doc}: {e}")

    print(f"Success: Synced {total_added} new items (Artifacts + Strategy) into Wisdom collection.")

if __name__ == "__main__":
    main()