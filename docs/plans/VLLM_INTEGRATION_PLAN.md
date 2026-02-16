# vLLM Integration Plan: The Unified Silicon Foundation [v2.0]
**Goal:** High-Throughput Bicameral Reasoning on the 11GB RTX 2080 Ti.

## 🏛️ The Unified Base Architecture
To maximize VRAM efficiency and leverage **Paged Attention**, the Lab utilizes an **Abstracted Model Hierarchy**. This allows the mind to grow and adapt as new models emerge without hardcoding logic.

*   **LARGE (High Fidelity):** Targeted for complex reasoning (e.g., Llama-3.2-3B).
*   **MEDIUM (Standard):** Current baseline for concurrent nodes (e.g., Gemma 2 2B).
*   **SMALL (Lite):** Low-footprint triage during multi-use peaks (e.g., Llama-3.2-1B).
*   **VRAM Target:** < 2.5 GB baseline for the Large tier (AWQ), ensuring a ~30% VRAM headroom buffer for sensory nodes (EarNode).
*   **The Strategy:** Standardize nodes on the **Abstract Tier** rather than specific weight files. The Lab Attendant manages the mapping via `vram_characterization.json`.

## 🪜 The Resilience Ladder (Degradation Order)
The Lab MUST remain available even during heavy multi-use scenarios (e.g., Jellyfin transcodes, Steam gaming).

| Tier | Engine | Model | Purpose |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Fidelity)** | vLLM | Gemma 2 2B | Full Bicameral Logic with Paged Attention. |
| **Tier 2 (Fallback)** | Ollama | Gemma 2 2B | Engine Swap. Stable baseline if vLLM becomes unstable. |
| **Tier 3 (Downshift)** | Ollama | Llama-3.2-1B | High VRAM pressure. Triage only. |
| **Tier 4 (Hibernation)**| None | N/A | SIGTERM/Suspend. GPU 100% reserved for user tasks. |

## 🧠 Cognitive Logic (The Amygdala v3)
We have moved beyond brittle word counts. Worthiness is now determined by **Intent & Context**.

### 1. Contextual Double-Take (The "Who am I?" Check)
When "Brain" is mentioned, the node performs an internal audit:
*   **Social Context:** Is the user talking about the character "The Brain" (the mouse)?
*   **Strategic Context:** Is the user asking for technical depth or strategic reasoning?
*   **Action:** Interject only on Strategic Context.

### 2. Dissonance Detection
The Brain monitors Pinky's triage. If Pinky provides a high-enthusiasm but low-fidelity response to a query that maps to a **Strategic Pillar** (God View), the Brain automatically interjects to provide the "Lead Engineer" perspective.

### 3. Scar-Tissue Triggers
Immediate wake-up on keywords related to project failures or high-stakes validation:
*   `regressions`, `silicon failure`, `unstable drivers`, `race conditions`.

## 🛠️ Performance Mandates
*   **Liger-Gemma Optimization:** Use Liger-Kernels to optimize Gemma 2 2B weights, maximizing the available **Paged Attention** pool for concurrent node access.
*   **Transition Space Cooldown:** The Lab Attendant MUST implement an explicit "Cooldown" cycle. When a session ends, the Attendant will trigger a KV cache purge (or engine reload) to prevent fragmentation before the system returns to "Slow Burn" monitoring.
*   **Multi-LoRA Support:** Required for all nodes to share the Gemma 2 2B base.
*   **Emergency Cache Eviction:** If non-AI GPU load is detected, the Attendant must shrink the vLLM KV cache to `--max-num-seqs 1` before resorting to SIGTERM.
