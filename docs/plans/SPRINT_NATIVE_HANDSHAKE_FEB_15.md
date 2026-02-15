# 🏃 Sprint Plan: Project "Native Handshake" (Feb 15, 2026) [v1.1]
**"Full-Stack Silicon Validation & Native Tooling"**

## 🎯 Objective
To transition the Federated Lab to **Native LLM Tool Calling** while hardening the environment through **Full-Stack SMOKE** verification. This ensures the "Mice" use industry-standard schemas and that the Lab's stability is verified across the *entire* resident stack before any human interaction.

---

## 🏗️ The "Golden Gate" (Stability Gates)
1.  **Gate 1: DEBUG_SMOKE.** (Task 0.1) Non-interactive. Loads Archive + Pinky + Brain + Architect. Quits immediately on success.
2.  **Gate 2: GUI_WORKOUT.** (test_gui_flows.py) Automated interactive test. Verifies Handshake -> Sync -> Tool Call -> Answer.
3.  **Gate 3: SILICON_SOAK.** (test_lifecycle_gauntlet.py) Stress test for VRAM and network resilience.

---

## 🏎️ Phase 0: Environment Hardening
**Goal:** Fix the "False Positive" smoke test.

*   **Task 0.1: Full-Stack SMOKE.** Update `acme_lab.py`. Remove the "Fast-Boot" shortcut. `DEBUG_SMOKE` must initialize **every** resident node before self-terminating.
*   **Verification:** Run `python3 acme_lab.py --mode DEBUG_SMOKE`. It must log successful initialization for all 4 nodes.

## 🏎️ Phase 1: Native Baseline (The Schema Shift)
**Goal:** Prove Native Tool Calling on the Archive Node.

*   **Task 1.1: Schema Generation.** Update `BicameralNode` (`loader.py`) to auto-generate OpenAI-style tool schemas from the `mcp` manager.
*   **Task 1.2: Native vLLM Call.** Refactor `generate_response` to send the `tools` array.
*   **Task 1.3: NVML Vibe Check.** Update Pinky's `vram_vibe_check` to use direct `pynvml` bindings.
*   **Verification:** `src/debug/test_native_handshake.py` + Full-Stack SMOKE.

## 🎭 Phase 2: Amygdala v3 (Personality & Commentary)
**Goal:** Restore the "Right Hemisphere" as an intuitive partner.

*   **Task 2.1: Contextual Peeking.** Implement "Right Hemisphere Pass" in `acme_lab.py`. Pinky provides live contextual commentary before the Brain's reasoning block.
*   **Task 2.2: The "Directness" Rule.** Hub-level enforcement: "Direct Answer First."
*   **Verification:** `src/debug/test_contextual_echo.py` + `src/debug/test_pi_flow.py`.

## 🔪 Phase 3: Hub Refactor (The Native Dispatcher)
**Goal:** Retirement of the "Architect Triage" middleman.

*   **Task 3.1: Tool Unwrapped.** Update `execute_dispatch` to handle the native `tool_calls` object.
*   **Task 3.2: Error Hallucination Trap.** Maintain the v3.8.3 "Lost Gem" interceptor for `McpError`.
*   **Verification:** `test_gui_flows.py` (The WORKOUT).

## 🛡️ Phase 4: Validation Gauntlet
**Goal:** multi-tenancy verification.

*   **Task 4.1: Silicon Stability.** `test_apollo_vram.py` (KV Cache check).
*   **Task 4.2: Pre-emption.** `test_sigterm_protocol.py` (Gaming/Steam suspension).
*   **Final:** `test_lifecycle_gauntlet.py`.

---

## 📜 Active Protocols
- **Safe-Scalpel (BKM-011):** Use `atomic_patcher.py`.
- **Lost Gem (v3.1.9):** Restore explicit UI status: `[LOBBY]`, `[TRIAGE]`, `[SYNTHESIS]`.
