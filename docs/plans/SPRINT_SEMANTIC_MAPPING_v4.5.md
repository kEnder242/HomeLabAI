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

## 🧪 4. Verification & Test Audit
Every feature must be verified against the existing suite or new targeted tests.

| Feature | Primary Test Script | Strategy |
| :--- | :--- | :--- |
| **ChromaDB / RAG** | `src/test_memory_integration.py` | Verify end-to-end vector lookup. |
| **Dreaming Cycle** | `src/test_dream.py` | Validate log-to-wisdom synthesis pipeline. |
| **Liger Kernels** | `src/test_liger.py` | Bench-test fused kernels on Turing. |
| **Year Triggers** | `src/debug/test_year_recall.py` | **[NEW]** Verify "2019" query triggers recall. |
| **Internal Debate**| **[NEW]** `src/debug/test_debate.py`| Verify node consensus over vector history. |

---

## 📅 5. Tasks
- [x] **Task 1: Memory Resurrection (ChromaDB).** [DONE] Re-plugged vector store to `archive_node.py`.
- [x] **Task 2: Silicon Optimization (Liger).** [DONE] Integrated fused kernels in `loader.py`.
- [ ] **Task 3: Folder-First UI.** Restrict Filing Cabinet to shared active directories (Whiteboard/Drafts/Manual).
- [ ] **Task 4: Semantic Triggers.** Implement the Amygdala Year-Scanner for automatic 18-year recall.
- [ ] **Task 5: Live Internal Debate.** Register the debate engine as an active tool for high-fidelity peer review.
- [ ] **Task 6: Dream & Synthesis Audit.** Verify background `dream_cycle.py` multi-host handoff to Windows 4090.

---
*Reference: [HomeLabAI/docs/Protocols.md](../Protocols.md)*
