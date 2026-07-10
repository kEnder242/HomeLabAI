#!/usr/bin/env python3
import os
import sys
import logging
import chromadb
from chromadb.utils import embedding_functions

DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_DNA = "behavioral_dna"
COLLECTION_FEATURE = "feature_dna"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def get_safe_collection(client, name, ef):
    try:
        return client.get_or_create_collection(name=name, embedding_function=ef)
    except Exception:
        return client.get_or_create_collection(name=name)

def test_retrieval():
    print("=== [TEST] ClaraDB (ChromaDB) DNA Tooling Verification ===")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ ERROR: Database directory not found at {DB_PATH}")
        print("💡 Debug: Verify if AcmeLab is mounted or initialized correctly.")
        sys.exit(1)
        
    print(f"🔌 Connecting to ChromaDB at {DB_PATH}...")
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Check collections
    cols = [c.name for c in client.list_collections()]
    print(f"📁 Collections in DB: {cols}")
    
    if COLLECTION_DNA not in cols:
        print(f"❌ ERROR: Collection '{COLLECTION_DNA}' is missing!")
        print("💡 Debug: Run `sync_chroma_dna.py` to initialize and sync collections.")
        sys.exit(1)
        
    if COLLECTION_FEATURE not in cols:
        print(f"❌ ERROR: Collection '{COLLECTION_FEATURE}' is missing!")
        print("💡 Debug: Run `sync_chroma_dna.py` to initialize and sync collections.")
        sys.exit(1)
        
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # 1. Test behavioral_dna (BKMs)
    print("\n🔍 Querying behavioral_dna (BKMs)...")
    col_dna = get_safe_collection(client, COLLECTION_DNA, ef)
    dna_count = col_dna.count()
    print(f"   Count of documents in '{COLLECTION_DNA}': {dna_count}")
    if dna_count == 0:
        print(f"❌ ERROR: Collection '{COLLECTION_DNA}' is empty!")
        print("💡 Debug: Run a git commit or manually execute `python3 sync_chroma_dna.py` to parse Protocols.md.")
        sys.exit(1)
        
    # Query for atomic patching
    query_bkm = "atomically patch files or safe scalpel"
    print(f"   Searching for: '{query_bkm}'...")
    res_bkm = col_dna.query(query_texts=[query_bkm], n_results=1)
    
    if res_bkm and res_bkm["documents"] and res_bkm["documents"][0]:
        doc = res_bkm["documents"][0][0]
        meta = res_bkm["metadatas"][0][0]
        distance = res_bkm["distances"][0][0]
        print(f"   ✅ SUCCESS: Found BKM match (Distance: {distance:.4f})")
        print(f"      Matched ID: {meta.get('bkm_id')} - Name: {meta.get('name')}")
        print(f"      Snippet: {doc.splitlines()[3] if len(doc.splitlines()) > 3 else doc}")
    else:
        print("❌ ERROR: Query returned no results!")
        sys.exit(1)
        
    # 2. Test feature_dna (Features)
    print("\n🔍 Querying feature_dna (Features/Vibes)...")
    col_feat = get_safe_collection(client, COLLECTION_FEATURE, ef)
    feat_count = col_feat.count()
    print(f"   Count of documents in '{COLLECTION_FEATURE}': {feat_count}")
    if feat_count == 0:
        print(f"❌ ERROR: Collection '{COLLECTION_FEATURE}' is empty!")
        sys.exit(1)
        
    # Query for RAPL
    query_feat = "RAPL simulator validation telemetry"
    print(f"   Searching for: '{query_feat}'...")
    res_feat = col_feat.query(query_texts=[query_feat], n_results=1)
    
    if res_feat and res_feat["documents"] and res_feat["documents"][0]:
        doc = res_feat["documents"][0][0]
        meta = res_feat["metadatas"][0][0]
        distance = res_feat["distances"][0][0]
        print(f"   ✅ SUCCESS: Found Feature match (Distance: {distance:.4f})")
        print(f"      Matched ID: {meta.get('feature_id')} - Name: {meta.get('name')}")
        print(f"      Snippet: {doc.splitlines()[3] if len(doc.splitlines()) > 3 else doc}")
    else:
        print("❌ ERROR: Query returned no results!")
        sys.exit(1)
        
    print("\n🏆 ClaraDB DNA Tooling Verification: ALL TESTS PASSED.")

if __name__ == "__main__":
    test_retrieval()
