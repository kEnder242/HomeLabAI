# 🏃 Sprint Plan: Project Awakening [v4.5/v4.9 Hybrid]
**"The Unified Base / Multi-LoRA Restoration"**

## 🎯 Objective
To stabilize **Multi-LoRA Paged Attention** using an efficient unified base (e.g., Llama-3.2-3B via local GGUF blob) to restore the "Unity" pattern where all concurrent Lab nodes share a single VRAM footprint, freeing up space for the NeMo EarNode.

---

## 🏗️ The Diamond Gate (Verification Gauntlet)
1.  **Gate 1: UNITARY_SHUTDOWN.** `AsyncExitStack` managed in unitary task (Verified).
2.  **Gate 2: FEDERATED_FAILOVER.** KENDER @ `.26` with local fallback (Verified).
3.  **Gate 4: STRATEGIC_SENTINEL.** Brain engages on keywords (regression, silicon) (Verified).
4.  **Gate 5: MULTI_LORA_PROBE.** [IN PROGRESS] Concurrent LoRA residency on 11GB VRAM.
5.  **Gate 6: BARGE_IN.** "Wait, stop" kills current generation (Verified).
6.  **Gate 7: APOLLO_VRAM.** Confirmed KV cache stability via `test_apollo_vram.py` (Pending Stability).

---

## 🏎️ Phase 1: Silicon Multi-Tenancy (Infrastructure)
*   [DONE] **Task 1.0: Weight Recovery**. Identified Ollama blob `sha256-74627347...` as a viable Llama 3.2 3B GGUF candidate.
*   [TODO] **Task 1.1: Multi-LoRA Initialization**. Re-point `start_vllm.sh` to the verified local blob with `--load-format gguf`.
*   [TODO] **Task 1.2: resolve_ip() Implementation**. Refactor `loader.py` for dynamic KENDER resolution.
*   **Verification:** `test_federated_failover.py` (Rerun).

## 🎭 Phase 2: Hemispheric Awakening (The Soul)
*   [DONE] **Task 2.1: Parallel Dispatch v2**. Refactor `process_query` for concurrent Pinky/Brain awareness.
*   [DONE] **Task 2.2: Barge-In Watchdog**. Implement interrupt signal handling in Hub.
*   [DONE] **Task 2.3: Brain Addressing**. Verify "Brain" mention triggers handover + persona response.
*   [TODO] **Task 2.4: Semantic Map Consumption**. Connect Pinky to Architect's strategic map.
*   **Verification:** `test_strategic_interjection.py` (Verified).

## 🛡️ Phase 3: Validation & Vetting
*   [TODO] **Task 3.1: The Gauntlet**. Run all 7 Diamond Gate tests.
*   **Final:** Full-Stack verification with KENDER online.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **Unitary Task:** `AsyncExitStack` must be managed in a single task.
- **Silicon Strategy:** vLLM is Primary for concurrent node efficiency. Model selection is a tunable knob for VRAM optimization.
- **Unity Pattern:** All concurrent nodes MUST share the same model base.
