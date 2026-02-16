# 🏃 Sprint Plan: Unity Stabilization [v4.2]
**"The 11GB VRAM Gauntlet: Multi-LoRA & Paged Attention"**

## 🎯 Objective
Stabilize the **Unity Pattern** on the 11GB RTX 2080 Ti. This involves running the full Bicameral Mind (4 nodes) on a shared **Llama-3.2-3B** base via vLLM, utilizing **Liger-Kernels** and **Paged Attention** to fit alongside the NeMo EarNode.

---

## 🏛️ The Unity Pattern (Core Mandate)
All concurrent resident nodes (Pinky, Brain, Archive, Architect) MUST share the same underlying model base in vLLM to maximize VRAM efficiency. Model selection is a tunable knob, but **Llama-3.2-3B-AWQ** is the current best-fit candidate.

---

## 🏗️ The Diamond Gate (Verification Gauntlet)
1.  **Gate 1: GGUF_BYPASS.** vLLM loads the local Ollama blob (`sha256-74627347...`) via `--load-format gguf`.
2.  **Gate 2: LIGER_UNIFORMITY.** Model-aware Liger-Kernels applied to the unified base.
3.  **Gate 3: SHARED_FOOTPRINT.** 4 nodes + EarNode resident at < 10.5GB VRAM.
4.  **Gate 4: STRATEGIC_SENTINEL.** Amygdala v3 triggers Brain on "silicon/regression" keywords.
5.  **Gate 5: BARGE_IN.** Interrupt logic ceased generation < 200ms on "STOP" keyword.
6.  **Gate 6: MEMORY_BRIDGE.** Brain receives last 3 turns of context during handover.

---

## 🏎️ Phase 1: Silicon Multi-Tenancy (Infrastructure)
*   [TODO] **Task 1.1: The GGUF Harvester**. Re-point `start_vllm.sh` to the verified local blob `/usr/share/ollama/.ollama/models/blobs/sha256-7462734796d67c40ecec2ca98eddf970e171dbb6b370e43fd633ee75b69abe1b`.
*   [TODO] **Task 1.2: VRAM Shaving**. Tune `--gpu-memory-utilization` (Target: 0.3-0.4) and `--max-model-len` to prevent OOM during concurrent node initialization.
*   [TODO] **Task 1.3: resolve_ip() Implementation**. Refactor `loader.py` for dynamic KENDER (4090) resolution to prevent hardcoded IP drifts.
*   **Verification:** `src/debug/test_apollo_vram.py`.

## 🎭 Phase 2: Hemispheric Awakening (The Soul)
*   [DONE] **Task 2.1: Parallel Dispatch v2**. Concurrent Pinky/Brain awareness in `process_query`.
*   [TODO] **Task 2.2: English-Only Validation**. Hard-code the "No Spanish" constraint into the system prompts to further reduce token logit overhead.
*   [TODO] **Task 2.3: Semantic Map Consumption**. Connect Pinky's triage to the Architect's `semantic_map.json` for grounded retrieval.
*   **Verification:** `src/debug/test_strategic_interjection.py`.

## ⚡ Phase 3: Nervous System (Stability & Physics)
*   [TODO] **Task 3.1: VRAM Heartbeat**. Implement 10s sliding-window GPU load monitoring in `lab_attendant.py`.
*   [TODO] **Task 3.2: Shadow Dispatch**. Prototype predictive background generation for the Brain while user is still speaking (Only if VRAM < 8GB).
*   **Verification:** `src/debug/test_lifecycle_gauntlet.py`.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **English-Only Catalyst:** Use English-optimized prompts to preserve the 11GB budget.
- **Unity Residency:** Never run concurrent nodes on disparate base models.
