# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026) [FINAL REVISION]
**"Native Silicon Tools, NVML Telemetry, & Personality-Driven Commentary"**

## 🎯 Objective
To transition the Federated Lab to **Native LLM Tool Calling** (OpenAI-compatible `tools` API) while hardening the **Bicameral Persona** and **Silicon Watchdog**. This replaces brittle regex triage with industry-standard schema execution, powered by **NVML** for millisecond hardware awareness.

---

## 🏛️ Architectural Pivot: The "Native Dispatcher"
| Feature | Current (Brittle) | Target (Native) |
| :--- | :--- | :--- |
| **Tool Definition** | Injected into System Prompt as text. | Native `tools[]` JSON Schema in API payload. |
| **Telemetry** | `nvidia-smi` binary (High Latency). | **NVML (pynvml)** (Raw C-Level Speed). |
| **Detection** | Regex/String matching in Architect Node. | Native `tool_calls` object from inference engine. |
| **Persona** | Randomized "Narf" interjections. | **Live Commentary**: Intuitive Right Hemisphere pass. |
| **Validation** | Manual `json.loads` in `acme_lab.py`. | Schema-validated via Pydantic/Native Engine. |

---

## 🏎️ Phase 1: Native Baseline (The Schema Shift)
**Goal:** Prove Native Tool Calling on the Archive Node.

*   **Task 1.1: Schema Generation.** Update `BicameralNode` (`loader.py`) to automatically generate OpenAI-style tool schemas from the `mcp._tool_manager`.
*   **Task 1.2: Native vLLM Call.** Refactor `generate_response` to send the `tools` array when the engine is `VLLM`.
*   **Task 1.3: NVML Vibe Check.** Update Pinky's `vram_vibe_check` to use direct NVML bindings instead of `nvidia-smi` parsing.
*   **Verification:**
    *   `src/debug/test_tool_registry.py`: Confirms tools are mapped correctly to JSON schemas.
    *   `src/debug/test_vllm_alpha.py`: Low-level connectivity check for the tool-aware endpoint.

## 🎭 Phase 2: Amygdala v3 (Personality & Commentary)
**Goal:** Restore the "Right Hemisphere" as an intuitive partner.

*   **Task 2.1: Contextual Peeking.** Implement "Right Hemisphere Pass" in `acme_lab.py`. Before Brain reasoning, Pinky "peeks" at the context and provides character-rich commentary.
*   **Task 2.2: The "Directness" Rule.** Update the Hub to enforce "Direct Answer First" (leveraging Task 5.1 from previous sprint).
*   **Verification:**
    *   `src/test_latency_tics.py`: Verifies interjection timing during long reasoning cycles.
    *   `src/debug/test_contextual_echo.py`: Ensures Pinky's commentary matches the session vibe.
    *   `src/debug/test_pi_flow.py`: **CRITICAL.** Verifies "Direct Answer First" (Result before Reasoning).

## 🔪 Phase 3: Hub Refactor (The Native Dispatcher)
**Goal:** Remove the "Architect Triage" middleman from `acme_lab.py`.

*   **Task 3.1: Tool Unwrapped.** Update `execute_dispatch` to handle the native `tool_calls` object directly.
*   **Task 3.2: Error Hallucination Trap.** Maintain the v3.8.3 "Lost Gem": Intercept `McpError` and force a re-triage if a tool fails.
*   **Verification:**
    *   `src/debug/test_dispatch_logic.py`: Passes with native objects.
    *   `src/debug/test_resurrection_tools.py`: Confirms CV Builder, BKM Generator, and History Access are functional in the new flow.

## 🛡️ Phase 4: Validation Gauntlet (The "Physician's Pass")
**Goal:** Full silicon stability and multi-tenancy verification.

*   **Task 4.1: Silicon Stability.** Run `test_apollo_vram.py` to ensure the new native overhead doesn't trip the 11GB budget.
*   **Task 4.2: Pre-emption Logic.** Verify `test_sigterm_protocol.py` correctly suspends engines during external load (Gaming/Steam).
*   **Final Pass:** `src/debug/test_lifecycle_gauntlet.py` (Resilience soak test).

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Use `atomic_patcher.py` for all edits.
- **Discuss with me (BKM-004):** HALT on any VRAM anomaly or NVML communication error.
- **Lost Gem (v3.1.9):** Restore explicit UI status messages: `[LOBBY]`, `[TRIAGE]`, `[SYNTHESIS]`.
