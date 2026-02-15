# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026) [v1.2]
**"Multi-LoRA Resurrection & Hemispheric Concurrency"**

## 🎯 Objective
To transition the Federated Lab to **Native LLM Tool Calling** while restoring **Multi-LoRA** residency and implementing **Hemispheric Concurrency**. This allows "The Brain" to autonomously monitor the vLLM stream, interject when addressed directly, and leverage the Windows 4090 (KENDER) as a high-fidelity failover.

---

## 🏛️ Architectural Pivot: Hemispheric Concurrency
| Feature | Current (Sequential) | Target (Concurrent) |
| :--- | :--- | :--- |
| **Control Flow** | Pinky decides if Brain wakes up. | **Parallel Dispatch**: Hub pings all nodes. |
| **Brain Awareness** | Dependent on `ask_brain` tool. | **Autonomous Monitoring**: Brain watches all input. |
| **Failover** | Local vLLM only. | **Federated Hub**: vLLM (Linux) <-> 4090 (Windows). |
| **Tooling** | Brittle regex triage. | Native OpenAI-compatible `tools[]` API. |

---

## 🏗️ Stability Gates
1.  **Gate 1: DEBUG_SMOKE.** Unitary task loading of Archive + Pinky + Brain + Architect.
2.  **Gate 2: MULTI_LORA_PROBE.** Verify vLLM handles concurrent LoRA requests.
3.  **Gate 3: FEDERATED_FAILOVER.** Verify Brain transitions to KENDER (4090) if Linux is busy.

---

## 🏎️ Phase 1: Silicon Multi-Tenancy (Multi-LoRA)
**Goal:** Restore LoRA residency on the 2080 Ti.

*   **Task 1.4: LoRA Base.** Update `start_vllm.sh` with `--enable-lora --max-loras 4`.
*   **Task 1.5: Node Identity.** Add `lora_name` to `BicameralNode` constructor in `loader.py`.
*   **Task 1.6: KENDER IP Update.** Codify dynamic resolution for KENDER at `192.168.1.26`.
*   **Verification:** `test_multi_lora_residency.py` (New).

## 🎭 Phase 2: Hemispheric Concurrency (The Soul)
**Goal:** Restore the Brain as an autonomous strategic partner.

*   **Task 2.3: Parallel Dispatch.** Refactor Hub (`acme_lab.py`) to send queries to Pinky & Brain nodes simultaneously.
*   **Task 2.4: Intent Triage.** Implement "Worthiness" logic in Brain node (Strategy vs. Social addressing).
*   **Verification:** `test_autonomous_interjection.py` (New).

## 🔪 Phase 3: Hub Refactor (Native Dispatcher)
**Goal:** Retirement of the "Architect Triage" middleman.

*   **Task 3.1: Tool Unwrapped.** Update `execute_dispatch` to handle the native `tool_calls` object.
*   **Task 3.3: Federated Failover.** Refactor `loader.py` to seamlessly fallback to 4090 if local vLLM OOMs.
*   **Verification:** `test_gui_flows.py` (The WORKOUT).

## 🛡️ Phase 4: Validation Gauntlet
**Goal:** Full silicon stability verification.

*   **Task 4.1: Silicon Stability.** `test_apollo_vram.py` (KV Cache + Multi-LoRA check).
*   **Final:** `test_lifecycle_gauntlet.py`.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Mandatory for all logic changes.
- **Unitary Task:** `AsyncExitStack` must be entered/exited in the same task.
- **KENDER Awareness:** 4090 is live at `192.168.1.26`.
