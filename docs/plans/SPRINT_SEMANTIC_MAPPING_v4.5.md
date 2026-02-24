# Sprint Plan: Semantic Mapping Reclamation [v4.5]
**Status:** ACTIVE
**Goal:** Restore vector-based memory, automated dreaming, and integrated Liger-Kernels.

---

## 🏎️ 1. Preparation (The One-Liners)
```bash
# 1. Verify ChromaDB persistence
ls -la ~/AcmeLab/chroma_db

# 2. Sequential Resident Loading (BKM-003)
# To avoid initialization deadlocks observed on Feb 15
# Order: Archive (Chroma) -> Pinky -> Brain
```

## 🧪 2. Core Logic: The Vector-Aware Archive
**Target**: `HomeLabAI/src/nodes/archive_node.py`

### **The "Lost" Snippet (Chroma Integration)**:
```python
# [BKM-015] Robust Chroma Loading
import chromadb
from chromadb.utils import embedding_functions

def get_safe_collection(name):
    try:
        return chroma_client.get_or_create_collection(
            name=name, 
            embedding_function=ef
        )
    except Exception as e:
        logging.warning(f"Chroma conflict: {e}. Fallback to generic.")
        return chroma_client.get_or_create_collection(name=name)
```

### **The Semantic Map Bridge**:
*   **Location**: `Portfolio_Dev/field_notes/data/semantic_map.json`
*   **Logic**: Map yearly anchors (e.g., "2019") to Rank 4 technical gems.
*   **Integration**: Pinky gateway must check the semantic map for "Year" or "Theme" keywords and prepend relevant gems to the Brain's prompt.

---

## ⚡ 3. Liger-Kernel Integration
**Target**: `HomeLabAI/src/nodes/loader.py`

### **Recovery Logic (from Feb 9 Bench-test)**:
```python
# [BKM-016] Liger Application
from liger_kernel.transformers import apply_liger_kernel_to_mistral, apply_liger_kernel_to_qwen2

def patch_model(model_id):
    if "mistral" in model_id.lower():
        apply_liger_kernel_to_mistral()
    elif "qwen" in model_id.lower():
        apply_liger_kernel_to_qwen2()
```
*   **Goal**: Apply patches *before* model load in the `BicameralNode` class.
*   **ROI**: ~80% VRAM reduction on Turing (`sm_75`).

---

## 🤕 4. Scars (The Feb 15 Snafu)
*   **OOM Deadlock**: Simultaneous node startup + ChromaDB loading killed the Lab.
*   **Space Collision**: Full drive corrupted the `.json` session save.
*   **Mitigation**: 
    1.  **Sequential Boot**: Orderly handshakes.
    2.  **Remote Brain**: Keep heavy weights on KENDER (4090); keep search/mapping on Z87.

---

## 📅 5. Tasks
- [ ] **Task 1: Re-Plug ChromaDB.** Restore vector collections to `archive_node.py`.
- [ ] **Task 2: Restore 'Dream' Tool.** Automated consolidation of short-term logs.
- [ ] **Task 3: Integrate Liger.** Update `loader.py` with architecture-aware patches.
- [ ] **Task 4: Amygdala Year-Triggers.** Enable instant recall for queries like "2019".

---
*Reference: [HomeLabAI/docs/Protocols.md](../Protocols.md)*
