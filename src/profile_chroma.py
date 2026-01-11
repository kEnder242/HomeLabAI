import time
import sys
import os

print(f"⏱️  [1/4] Starting Profiler (PID: {os.getpid()})...")
t0 = time.time()

print("⏱️  [2/4] Importing modules...")
import chromadb
from chromadb.utils import embedding_functions
t1 = time.time()
print(f"   ✅ Imports took: {t1 - t0:.2f}s")

DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
print(f"⏱️  [3/4] Initializing PersistentClient at {DB_PATH}...")
try:
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    t2 = time.time()
    print(f"   ✅ Client Init took: {t2 - t1:.2f}s")
except Exception as e:
    print(f"   ❌ Client Init FAILED: {e}")
    sys.exit(1)

print("⏱️  [4/4] Loading Embedding Function (all-MiniLM-L6-v2)...")
try:
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    t3 = time.time()
    print(f"   ✅ Model Load took: {t3 - t2:.2f}s")
except Exception as e:
    print(f"   ❌ Model Load FAILED: {e}")
    sys.exit(1)

print(f"🎉 Total Startup Time: {t3 - t0:.2f}s")
