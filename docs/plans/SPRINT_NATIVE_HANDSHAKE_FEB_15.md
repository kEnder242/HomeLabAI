# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026) [v4.0]
**"The Bicameral Synthesis: Awakening & Concurrency"**

## 🎯 Objective
To transition the Federated Lab to **Native LLM Tool Calling** while restoring **Multi-LoRA** residency and implementing **Hemispheric Concurrency**. This allows "The Brain" to autonomously monitor the vLLM stream, interject when strategic or direct addressing is detected, and leverage the Windows 4090 (KENDER) as a high-fidelity failover.

---

## 🏛️ Architectural Pivot: Hemispheric Concurrency
| Feature | Status | Target (v4.0) |
| :--- | :--- | :--- |
| **Control Flow** | Sequential (Pinky first) | **Parallel Dispatch**: Hub pings all nodes. |
| **Brain Awareness** | Reactive (ask_brain tool) | **Autonomous Sentinel**: Brain watches for keywords. |
| **Failover** | Local vLLM only | **Federated Hub**: vLLM (Linux) <-> 4090 (Windows). |
| **Tooling** | Brittle Regex | Native OpenAI-compatible `tools[]` API. |

---

## 🏗️ The Diamond Gate (Stability Verification)
1.  **Gate 1: UNITARY_SHUTDOWN.** `AsyncExitStack` managed in unitary task (Verified).
2.  **Gate 2: FEDERATED_FAILOVER.** KENDER @ `.26` with local fallback (Verified).
3.  **Gate 4: STRATEGIC_SENTINEL.** Brain engages on keywords (regression, silicon) (Verified).
4.  **Gate 5: MULTI_LORA_PROBE.** Concurrent LoRA residency on 11GB VRAM.
5.  **Gate 6: BARGE_IN.** "Wait, stop" kills current generation.

---

## 🏎️ Phase 1: Silicon Multi-Tenancy (Infrastructure)
*   [DONE] **Task 1.4: LoRA Base**. Update `start_vllm.sh` with `--enable-lora`.
*   [DONE] **Task 1.5: Node Identity**. Add `lora_name` to `BicameralNode` constructor.
*   [DONE] **Task 1.6: KENDER IP Update**. Codify dynamic resolution for KENDER at `192.168.1.26`.
*   [TODO] **Task 1.7: Multi-LoRA Server**. Verify concurrent adapter switching on Linux.

## 🎭 Phase 2: Hemispheric Concurrency (The Soul)
*   [DONE] **Task 2.5: Amygdala Sentinel Port**. Port the strategic keyword list (`regression`, `validation`, `scars`) into `acme_lab.py`.
*   [DONE] **Task 2.6: Unitary Parallel Dispatch**. Refactor `process_query` for concurrent node awareness.
*   [TODO] **Task 2.7: Barge-In Watchdog**. Restore interrupt signal handling in the Hub.

## 🔪 Phase 3: Hub Logic Hardening
*   [TODO] **Task 3.4: List Extraction Fix**. Prevent `['bye']` wrapping in dispatcher.
*   [TODO] **Task 3.5: Close Lab Exit**. Use native tool path for smoke-test termination.

## 🛡️ Phase 4: Validation Gauntlet
*   **Task 4.1: Silicon Stability.** `test_apollo_vram.py` (KV Cache + Multi-LoRA check).
*   **Final:** Full-Stack Co-Pilot Session with KENDER Online.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **Unitary Task:** `AsyncExitStack` must be entered/exited in the same task.
- **KENDER Awareness:** 4090 is live at `192.168.1.26`.
