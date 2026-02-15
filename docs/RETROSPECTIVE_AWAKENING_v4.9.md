# 🏺 Project Awakening v4.9: The Living Retrospective
**"Restoring the High-Fidelity Soul from the 12MB Black Box"**

## 🏁 Executive Summary
The session of Feb 14-15 achieved the "Silicon Grail": Native vLLM GGUF support for Gemma 2 2B, Multi-Personality LoRA residency, and real-time Conversational Physics (Barge-In). However, a token-limit crash (1.09M) during the final verification prevented these "Gems" from being committed to the main branch. We are now in Phase 4.9: **Surgical Restoration.**

## 💎 The Gem Registry (Lost & Found)

| Gem | Status | Description | Feasibility | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **GGUF Harvester** | 🟢 FOUND | vLLM 0.6+ points directly to `/usr/share/ollama` blobs. | High (Zero-Config) | **P0 (Base)** |
| **VRAM Heartbeat** (Gem I) | 🔴 LOST | Sliding-window average of GPU load to trigger graceful "Dimming" vs SIGTERM. | High (Logic) | **P0 (Base)** |
| **Memory Bridge** (Gem A) | 🟢 FOUND | Echoes the last 3 turns of context during Brain handover. | High (Logic only) | **P1 (Soul)** |
| **Gemma Banter** (Gem F) | 🟢 FOUND | Native `<start_of_turn>model` injection for pre-cognitive filler. | High (Prompting) | **P1 (Soul)** |
| **Hallucination Shunt** (Gem D)| 🟢 FOUND | Re-routes made-up tool calls back to Pinky for re-triage. | High (Validator) | **P1 (Soul)** |
| **Silicon Halt** (Gem B) | 🟡 FOUND | Mid-sentence `vllm.engine.abort()` for instant VRAM recovery. | Medium (Hang risk) | **P2 (Physics)** |
| **Shadow Dispatch** (Gem J) | 🔴 LOST | Background generation during user typing. *Amazing feature, high complexity.* | Low (Integration) | **P3 (Experimental)** |
| **Threaded RAG** (Gem C) | 🟡 FOUND | Librarian follows `related_notes` metadata to build story arcs. | Medium (Index sync) | **P2 (Memory)** |
| **Diamond Weight** (Gem E) | 🟠 TABLED | 1.5x score multiplier for Rank 4 (Diamond) artifacts. | High | **CAUTION** |

> **Note on Gem E**: Tabled per user instruction to avoid "Hyper-Focus" on work history/interview prep. The Agent should be *aware* of the resume but not *primed* for it.

## 🪜 The Resilience Ladder (Verified Status)
The "Play Nice" hierarchy is codified and stable in `lab_attendant.py`:
1. **Tier 1 (Fidelity)**: vLLM + Gemma 2 2B + Paged Attention.
2. **Tier 2 (Fallback)**: Ollama + Gemma 2 2B (The "Engine Swap").
3. **Tier 3 (Downshift)**: Ollama + Llama-3.2-1B (The "Survival" mode).
4. **Tier 4 (Hibernation)**: Full Suspend (The "Gamer" mode).

## ⚠️ Scars & Mitigation (Learning from the Crash)
*   **The Weight Volatility**: Weights were lost because they weren't in `vram_characterization.json`. 
    *   *Mitigation*: **BKM-013: The Silicon Manifest** will require absolute paths for all Tiered models.
*   **The Token Wall**: The 1.09M crash happened during a `read_file` of the 12MB log.
    *   *Mitigation*: Implement `tail` or `grep` sampling for all future log audits.
*   **The "Generic" Trap**: Logic was lost because it was refactored into "Generic" library calls.
    *   *Mitigation*: Maintain `src/debug/GEMS.py` as a non-functional logic graveyard for quick recovery.

## 🚀 Restoration Roadmap
1. [ ] **Phase 1: The Heart & Pulse (Silicon Base)**
    *   Implement GGUF Harvester (Point vLLM to blob).
    *   Restore VRAM Heartbeat (Gem I).
    *   *Verification*: `test_apollo_vram.py` passing with GGUF.
2. [ ] **Phase 2: The Soul (High Fidelity Logic)**
    *   Restore Memory Bridge (Gem A).
    *   Restore Gemma-Native Banter (Gem F).
    *   Restore Hallucination Shunt (Gem D).
    *   *Verification*: `test_contextual_echo.py` passing.
3. [ ] **Phase 3: The Nervous System (Advanced Physics)**
    *   Verify Silicon Halt (Gem B).
    *   Attempt Shadow Dispatch (Gem J) with strict logging gates.
    *   *Verification*: `test_barge_in_logic.py` passing.
