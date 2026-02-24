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
*   [x] **Task 1.1: The GGUF Harvester**. RE-POINTED to verified local blob.
*   [x] **Task 1.2: VRAM Shaving**. TUNED utilization (0.5) and max-model-len.
*   [x] **Task 1.3: resolve_ip() Implementation**. REFACTORED for dynamic KENDER resolution.
*   **Verification:** `src/debug/test_apollo_vram.py` [PASS].

## 🎭 Phase 2: Hemispheric Awakening (The Soul)
*   [x] **Task 2.1: Parallel Dispatch v2**. [COMPLETED] Concurrent Pinky/Brain awareness.
*   [ ] **Task 2.2: English-Only Validation**. [PURGED] Unnecessary with Llama-3.2-3B transition.
*   [x] **Task 2.3: Semantic Map Consumption**. [COMPLETED] Linked triage to 3-layer Semantic Map.
*   **Verification:** `src/debug/test_strategic_interjection.py` [PASS].

## ⚡ Phase 3: Nervous System (Stability & Physics)
*   [x] **Task 3.1: VRAM Heartbeat**. [COMPLETED] Native integration in Lab Attendant.
*   [x] **Task 3.2: Shadow Dispatch**. [COMPLETED] Multi-agent coordination with filler/quip sequence.
*   **Verification:** `src/debug/test_strategic_handover.py` [PASS].

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **English-Only Catalyst:** Use English-optimized prompts to preserve the 11GB budget.
- **Unity Residency:** Never run concurrent nodes on disparate base models.
