# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026) [REVISED]
**"Native Silicon Tools & Personality-Driven Commentary"**

## 🎯 Objective
To transition the Federated Lab to **Native LLM Tool Calling** (OpenAI-compatible `tools` API) while restoring the **Bicameral Persona**. This eliminates the "Architect Triage" middleman, fixes JSON leaks, and replaces robotic interjections with high-fidelity, personality-driven "Live Commentary" (Right Hemisphere pass).

---

## 🏛️ Architectural Pivot: The "Native Dispatcher"
| Feature | Current (Brittle) | Target (Native) |
| :--- | :--- | :--- |
| **Tool Definition** | Injected into System Prompt as text. | Native `tools[]` JSON Schema in API payload. |
| **Detection** | Regex/String matching in Architect Node. | Native `tool_calls` object from inference engine. |
| **Persona** | Randomized "Narf" interjections. | **Live Commentary**: Intuitive Right Hemisphere pass. |
| **Validation** | Manual `json.loads` in `acme_lab.py`. | Schema-validated via Pydantic/Native Engine. |

---

## 🏎️ Phase 1: Native Baseline (The Schema Shift)
**Goal:** Prove Native Tool Calling on the Archive Node.

*   **Task 1.1: Schema Generation.** Update `BicameralNode` (loader.py) to automatically generate OpenAI-style tool schemas from the existing `mcp._tool_manager` (referencing tools in `rundown_tools.md`).
*   **Task 1.2: Native vLLM Call.** Refactor `generate_response` to send the `tools` array when the engine is `VLLM`.
*   **Task 1.3: Ollama Schema Pass.** Verify Ollama/Windows correctly interprets the schema for Llama 3.1.
*   **Verification:** Create `src/debug/test_native_handshake.py` using the `ArchiveNode` as a test bed (listing 145 items).

## 🎭 Phase 2: Amygdala v3 (Personality & Commentary)
**Goal:** Restore the "Right Hemisphere" as an intuitive partner, not just a status checker.

*   **Task 2.1: Contextual Peeking.** Implement "Right Hemisphere Pass" in `acme_lab.py`. Before Brain reasoning, Pinky "peeks" at the context and provides enthusiastic live commentary.
    *   *Example:* "Narf! I'm seeing 2024 validation notes in the cabinet! I'll hand this over to The Brain for the deep scan."
*   **Task 2.2: Tone Sync.** Calibrate Pinky's interjections to scale with the Brain's complexity. If `deep_think` is active, Pinky provides progress "tics" (Poit!) to maintain session presence.
*   **Verification:** Run `src/test_latency_tics.py` and `src/debug/test_persona_logic.py`.

## 🔪 Phase 3: Hub Refactor (The Native Dispatcher)
**Goal:** Remove the "Architect Triage" middleman from `acme_lab.py`.

*   **Task 3.1: Tool Unwrapping.** Update `execute_dispatch` to handle the `tool_calls` object directly.
*   **Task 3.2: Triage Retirement.** Deprecate `architect.triage_response` for native calls. Keep as a fallback for small models (Llama 3.2 1B).
*   **Verification:** `src/debug/test_tool_registry.py` must pass with native objects.

## 🛡️ Phase 4: Validation Gauntlet (The "Physician's Pass")
**Goal:** 100% reliability across the federated stack.

*   **Task 4.1: Silicon Stability.** Run `src/debug/test_apollo_vram.py` to ensure Native Tooling doesn't exceed the 11GB budget.
*   **Task 4.2: Lifecycle Gauntlet.** Run `src/debug/test_lifecycle_gauntlet.py` to verify `aiohttp` resilience during tool-intensive sessions.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Use `atomic_patcher.py` for all edits.
- **Lost Gem (v3.1.9):** Restore the explicit "Handshake Status" messages in the UI console.
- **Silicon Law:** HALT on any `nvidia-smi` communication failure (BKM-004).
