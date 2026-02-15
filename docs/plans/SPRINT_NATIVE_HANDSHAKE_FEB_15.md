# 🏃 Sprint Plan: Project Awakening [v4.5]
**"The Gemma 2 / Multi-LoRA Restoration"**

## 🎯 Objective
To finalize the transition to **Native LLM Tool Calling** using **Gemma 2 2B** as the primary base for **Multi-LoRA Paged Attention**. This plan restores the "Lost Gems" of autonomous interjection and conversational physics while hardening the Federated Lab against regressions.

---

## 🏛️ Architectural Pivot: Hemispheric Concurrency
| Feature | Status | Target (v4.5) |
| :--- | :--- | :--- |
| **Primary Engine** | Sequential | **vLLM (Primary)** / Ollama (Backup). |
| **Model Mandate** | TBD | **Gemma 2 2B (Unified Base)**. Mistral is Forbidden. |
| **Control Flow** | Seq | **Parallel Dispatch**: Hub pings all nodes simultaneously. |
| **Brain Autonomy**| Reactive | **Strategic Sentinel**: Brain interjects on keywords. |
| **Tooling** | Regex | **Native OpenAI tools[]**: Unwrapped in Dispatcher. |

---

## 🏗️ The Diamond Gate (Verification Gauntlet)
1.  **Gate 1: UNITARY_SHUTDOWN.** `AsyncExitStack` managed in unitary task (Verified).
2.  **Gate 2: FEDERATED_FAILOVER.** KENDER @ `.26` with local fallback (Verified).
3.  **Gate 4: STRATEGIC_SENTINEL.** Brain engages on keywords (regression, silicon) (Verified).
4.  **Gate 5: MULTI_LORA_PROBE.** Concurrent LoRA residency on 11GB VRAM.
5.  **Gate 6: BARGE_IN.** "Wait, stop" kills current generation.
6.  **Gate 7: APOLLO_VRAM.** Confirmed KV cache stability via `test_apollo_vram.py`.

---

## 🏎️ Phase 1: Silicon Multi-Tenancy (Infrastructure)
*   [TODO] **Task 1.0: Weight Recovery**. Locate the directory containing Gemma 2 `config.json` and LoRA adapters.
*   [TODO] **Task 1.1: Multi-LoRA Initialization**. Update `start_vllm.sh` with the verified local path.
*   [TODO] **Task 1.2: resolve_ip() Implementation**. Refactor `loader.py` for dynamic KENDER resolution.
*   **Verification:** `test_federated_failover.py` (Rerun).

## 🎭 Phase 2: Hemispheric Awakening (The Soul)
*   [TODO] **Task 2.1: Parallel Dispatch v2**. Refactor `process_query` for concurrent Pinky/Brain awareness.
*   [TODO] **Task 2.2: Barge-In Watchdog**. Implement interrupt signal handling in Hub.
*   [TODO] **Task 2.3: Brain Addressing**. Verify "Brain" mention triggers handover + persona response.
*   **Verification:** `test_strategic_interjection.py` (Incorporate into CI).

## 🛡️ Phase 3: Validation & Vetting
*   [TODO] **Task 3.1: The Gauntlet**. Run all 7 Diamond Gate tests.
*   **Final:** Full-Stack verification with KENDER online.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **Unitary Task:** `AsyncExitStack` must be managed in a single task.
- **Silicon Law:** Mistral is Forbidden (11GB budget). vLLM is Primary.
- **KENDER Awareness:** 4090 is live at `192.168.1.26`.
