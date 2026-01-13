# src/preflight_check.py
import os
import sys
import logging

def prime_components():
    """
    Initializes heavy ML/DB components to warm up system caches.
    This should be run once before the main test suite.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [PREFLIGHT] %(levelname)s - %(message)s')

    # 1. Prime Sentence Transformer Model
    try:
        logging.info("Warming up Sentence Transformer...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        logging.info("✅ Sentence Transformer model loaded and cached.")
    except Exception as e:
        logging.error(f"❌ Failed to load Sentence Transformer: {e}")
        sys.exit(1)

    # 2. Prime ChromaDB
    try:
        logging.info("Warming up ChromaDB connection...")
        import chromadb
        db_path = os.path.expanduser("~/AcmeLab/chroma_db")
        client = chromadb.PersistentClient(path=db_path)
        # Touch a collection to ensure connection is live
        client.get_or_create_collection(name="preflight_check")
        logging.info("✅ ChromaDB connection established.")
    except Exception as e:
        logging.error(f"❌ Failed to connect to ChromaDB: {e}")
        sys.exit(1)

    logging.info("✅ Pre-flight check complete. All components are warm.")

if __name__ == "__main__":
    prime_components()
