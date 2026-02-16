> [!CAUTION]
> **STALE DOCUMENT:** This plan has been superseded by [SPRINT_UNITY_STABILIZATION_FEB_15.md](./SPRINT_UNITY_STABILIZATION_FEB_15.md).

# Sprint Plan: Project "Resurrection" (Feb 15, 2026)
**Goal:** Restore the High-Fidelity "Soul" and "Silicon Heart" of the Federated Lab.

## 🏁 Phase 1: The Heart & Pulse (Silicon Base)
**Objective**: Stabilize the 11GB VRAM budget using Native GGUF and Sliding-Window Throttling.

### Task 1.1: The GGUF Harvester (Gem P0)
*   **Action**: Update `start_vllm.sh` to point directly to the local Ollama blob (`/usr/share/ollama/...`).
*   **Logic**: Bypass HuggingFace/Safetensors entirely. Use `vllm >= 0.6.0` native GGUF loading.
*   **Verification**: `src/debug/test_apollo_vram.py` must boot successfully with < 2.5GB VRAM usage.

### Task 1.2: The VRAM Heartbeat (Gem I)
*   **Action**: Restore the `check_vram_heartbeat()` function in `lab_attendant.py`.
*   **Logic**: Implement a 10-second sliding window average of GPU load. 
*   **Trigger**: If `avg_load > 20%` (non-AI), trigger `vllm_engine.abort_request()` (Soft Dimming) instead of `SIGTERM`.
*   **Verification**: Run `steam` (or `glxgears`) and verify that vLLM stays alive but latency increases (Dimming), rather than crashing.

---

## 🎭 Phase 2: The Soul (High Fidelity Logic)
**Objective**: Restore the nuanced personality and cognitive continuity of the Bicameral Mind.

### Task 2.1: The Memory Bridge (Gem A)
*   **Action**: Modify `brain_node.py` to accept `context_window` from Pinky.
*   **Logic**: When `ASK_BRAIN` is triggered, Pinky MUST append the last 3 turns of the `history` list to the prompt.
*   **Verification**: `src/debug/test_contextual_echo.py` must show the Brain referencing a detail from 2 turns ago.

### Task 2.2: Gemma-Native Banter (Gem F)
*   **Action**: Update `pinky_node.py` system prompt.
*   **Logic**: Inject `<start_of_turn>model` tokens with pre-filled banter (e.g., *Pinky adjusts his goggles...*) to force the model into character immediately.
*   **Verification**: `src/debug/test_persona_logic.py` must return responses starting with valid roleplay actions.

### Task 2.3: The Hallucination Shunt (Gem D)
*   **Action**: Add a Pydantic Validator to `acme_lab.py`.
*   **Logic**: If `tool_name` is not in `registry`, return a structured `RetryRequest` to Pinky with the error "Tool not found, please re-triage."
*   **Verification**: Send a fake tool call (e.g., `use_magic_wand`) and verify Pinky apologizes and tries a valid tool.

---

## ⚡ Phase 3: The Nervous System (Experimental Physics)
**Objective**: Implement advanced, real-time interrupt logic.

### Task 3.1: Silicon Halt (Gem B)
*   **Action**: Connect the `STOP` keyword in `ear_node.py` to `vllm_client.abort()`.
*   **Logic**: Send a high-priority HTTP cancellation to the vLLM engine.
*   **Verification**: Start a long poem generation and shout "STOP." Verify token generation ceases < 200ms.

### Task 3.2: Shadow Dispatch (Gem J)
*   **Action**: Implement `background_task.create_task(brain.reason())` on `HEARING` state.
*   **Logic**: Start generating the Brain's response while the user is still typing (prediction).
*   **Gate**: Only active if `VRAM < 8GB`.
*   **Verification**: `src/debug/test_shadow_dispatch.py`. Log the time delta between "User Stop" and "Brain Start."

---

## 🛡️ Verification Gauntlet
Before calling this Sprint complete, run:
1.  `src/debug/test_lifecycle_gauntlet.py` (Stability)
2.  `src/debug/test_barge_in_logic.py` (Physics)
3.  `src/debug/test_contextual_echo.py` (Continuity)
