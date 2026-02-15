# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026)
**"Moving from String Triage to Native Silicon Tools"**

## 🎯 Objective
To transition the Federated Lab from a brittle "String-Matching" tool pattern to **Native LLM Tool Calling** (OpenAI-compatible `tools` API). This will eliminate JSON leaks, reduce latency by removing the "Architect Triage" hop, and restore high-fidelity "Banter" through calibrated interjection loops.

---

## 🏛️ Architectural Pivot: The "Native Dispatcher"
| Feature | Current (Brittle) | Target (Native) |
| :--- | :--- | :--- |
| **Tool Definition** | Injected into System Prompt as text. | Passed as `tools[]` JSON schema in the API call. |
| **Detection** | Regex extraction in `architect_node.py`. | Native `tool_calls` object from vLLM/Ollama. |
| **Execution** | Manual `json.loads` in `acme_lab.py`. | Automated dispatch via structured payload. |
| **Banter** | Random "Narf" interjections with decay. | Reactive "Double-Take" based on dissonance detection. |

---

## 🏎️ Phase 1: Native Baseline (The Schema Shift)
**Goal:** Prove Native Tool Calling on a single node (Archive Node).

*   **Task 1.1: Schema Generation.** Update `BicameralNode` (loader.py) to automatically generate OpenAI-style tool schemas from the `mcp._tool_manager`.
*   **Task 1.2: Native vLLM Call.** Refactor `generate_response` to send the `tools` array when the engine is `VLLM`.
*   **Task 1.3: Ollama Schema Pass.** Verify Ollama/Windows correctly interprets the schema for Llama 3.1.
*   **Test:** Create `src/debug/test_native_handshake.py` to verify the model returns a `tool_calls` object, not raw text.

## 🔪 Phase 2: Hub Refactor (The Native Dispatcher)
**Goal:** Remove the "Architect Triage" middleman from `acme_lab.py`.

*   **Task 2.1: Tool Unwrapping.** Update `execute_dispatch` to handle the `tool_calls` object directly from the node response.
*   **Task 2.2: Triage Retirement.** Deprecate `architect.triage_response` for native calls. Keep it ONLY as a fallback for non-native models.
*   **Test:** `src/debug/test_dispatch_logic.py` (Updated) must pass with native tool objects.

## 🎭 Phase 3: Banter Restoration (Amygdala v3)
**Goal:** Fix the "Narf Loop" using Dissonance Detection.

*   **Task 3.1: Dissonance Trigger.** Implement a check in `acme_lab.py` that triggers a "Pinky Double-Take" if the Brain's response contradicts the current user context (e.g., code vs. history).
*   **Task 3.2: TTL Calibration.** Fine-tune the Weighted TTL in the `reflex_loop` to ensure "Narf!" interjections occur exactly 15% of the time, increasing to 40% if the Brain is "Condescending."
*   **Test:** `src/test_latency_tics.py` (Updated) to verify interjection frequency.

## 🛡️ Phase 4: Validation Gauntlet (AFK Stability)
**Goal:** Ensure 100% reliability during autonomous sprints.

*   **Task 4.1: The Gauntlet.** Run `src/debug/test_lifecycle_gauntlet.py`.
*   **Task 4.2: Tool Registry Pass.** Run `src/debug/test_tool_registry.py` to confirm all 14 nodes/tools are correctly indexed by the new Native Dispatcher.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Use `atomic_patcher.py` for all logic changes.
- **Archive Node (BKM-012):** Use `patch_file` for complex diffs.
- **Discuss with me (BKM-004):** HALT on VRAM or Driver errors.

## 💎 Lost Gems (Git Mining Re-Integration)
*   **v3.1.9 "Handshake"**: Re-adopt the explicit "Wait for Triage" status messages that were lost in v3.6.
*   **v3.8.3 "Hallucination Trap"**: Maintain the `McpError` interceptor as a safety net for native tool failure.
