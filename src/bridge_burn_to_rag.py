import json
import os
import glob
import chromadb
import logging
import hashlib
import sys

# Set up paths for internal imports
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LAB_DIR not in sys.path:
    sys.path.append(LAB_DIR)
from infra.pager_relay import trigger_pager

# Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
PORTFOLIO_ROOT = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_WISDOM = "long_term_wisdom"

logging.basicConfig(level=logging.INFO)

def main():
    print("--- Bridging 'Slow Burn' Artifacts & Strategic Stories to RAG ---")
    trigger_pager("RAG Sync Started: Bridging slow burn artifacts and strategic stories...", source="RAG", severity="INFO")

    # 1. Init Chroma (Server-side embedding via ChromaDB HTTP server on port 8001)
    try:
        chroma_client = chromadb.HttpClient(host="127.0.0.1", port=8001)
        chroma_client.heartbeat()
    except Exception:
        chroma_client = chromadb.PersistentClient(path=DB_PATH)

    try:
        wisdom = chroma_client.get_or_create_collection(name=COLLECTION_WISDOM)
    except ValueError:
        wisdom = chroma_client.get_collection(name=COLLECTION_WISDOM)

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
                gem = event.get('technical_gem', '')
                evidence = event.get('evidence', '')
                date = event.get('date', 'Unknown')

                domain = event.get('domain', '')
                if not domain:
                    text_lower = (summary + ' ' + gem + ' ' + evidence).lower()
                    if any(k in text_lower for k in ['telemetry', 'prometh', 'dcgm', 'rapl', 'vram', 'power']):
                        domain = 'exp_tlm'
                    elif any(k in text_lower for k in ['bkm', 'validation', 'benchmark', 'test', 'verification']):
                        domain = 'exp_bkm'
                    elif any(k in text_lower for k in ['forensic', 'crash', 'bf16', 'turing', 'error']):
                        domain = 'exp_for'
                    else:
                        domain = 'sys_arch'

                # High-density content block for RAG
                content = f"[{date}] [{domain}] {summary}"
                if gem: content += f"\nTECHNICAL GEM: {gem}"
                if evidence: content += f"\nEVIDENCE: {evidence}"

                event_id = f"artifact_{hashlib.md5(content.encode()).hexdigest()}"

                if not wisdom.get(ids=[event_id])['ids']:
                    wisdom.add(
                        documents=[content],
                        metadatas=[{"source": fname, "date": date, "type": "artifact", "domain": domain}],
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

    # 5. Sync Asset Catalog (Artifacts)
    artifact_files = glob.glob(os.path.join(FIELD_NOTES_DATA, "artifacts_*.json"))
    for fpath in artifact_files:
        fname = os.path.basename(fpath)
        try:
            with open(fpath, 'r') as f:
                data = json.load(f)
            if not isinstance(data, list): continue

            for item in data:
                filename = item.get('filename', 'Unknown')
                synopsis = item.get('synopsis', '')
                keywords = item.get('keywords', [])
                rank = item.get('rank', 0)
                
                if not synopsis: continue

                # High-density asset block
                content = f"[ASSET: {filename}] {synopsis}"
                if keywords: content += f"\nKEYWORDS: {', '.join(keywords)}"
                if rank >= 3: content += f" [RANK: {rank}]"

                asset_id = f"asset_{hashlib.md5(content.encode()).hexdigest()}"

                if not wisdom.get(ids=[asset_id])['ids']:
                    wisdom.add(
                        documents=[content],
                        metadatas=[{"source": fname, "filename": filename, "type": "asset_catalog"}],
                        ids=[asset_id]
                    )
                    total_added += 1
        except Exception as e:
            print(f"Error processing artifact catalog {fname}: {e}")

    print(f"Success: Synced {total_added} new items (Artifacts + Strategy + Assets) into Wisdom collection.")
    trigger_pager(f"RAG Sync Complete: Synced {total_added} new items to long_term_wisdom.", source="RAG", severity="INFO")

if __name__ == "__main__":
    main()
