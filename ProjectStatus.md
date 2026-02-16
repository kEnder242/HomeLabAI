# Home Lab AI: Project Status (Feb 14, 2026)

## Current Core Architecture: v4.1 "Abstracted Silicon"
*   **Orchestration**: Managed via **`lab-attendant.service` (systemd)**.
    *   **Telemetry**: Native **NVML** (pynvml) for millisecond hardware watchdog.
    *   **Resilience Ladder**: 4-Tier hierarchy (vLLM -> Ollama -> Downshift -> Suspend).
    *   **Abstract Tiers**: Model-agnostic S/M/L mapping via `vram_characterization.json`.
*   **The Communication Hub (Corpus Callosum)**:
    *   **Unified Base**: Targeted transition to **Llama-3.2-3B** (via local GGUF) for 2080 Ti Unity Pattern.
    *   **Amygdala v3**: (In Progress) Intelligent interjection based on Dissonance Detection.

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | Version 570.211.01 (CUDA 12.8) |
| **Lab Attendant** | ✅ STABLE | Watchdog @ 2s; Abstract tiering verified. |
| **Resilience**    | ✅ VERIFIED | Engine Swap and Tier 3 Downshift tests passing. |
| **Archive Node** | ✅ STABLE | Librarian/Evidence Retrieval logic hardened. |
| **EarNode (STT)** | ✅ STABLE | NeMo 0.6B resident at ~1GB VRAM. |
| **Web Console** | ✅ STABLE | Handshake and [BICAMERAL HANDOVER] context verified. |

## Active Sprint: Unity Stabilization [v4.2] (Feb 15, 2026)
**Objective: Stabilize Multi-LoRA and Paged Attention on the 11GB RTX 2080 Ti.**
**Master Plan:** **[Sprint Plan: Unity Stabilization](docs/plans/SPRINT_UNITY_STABILIZATION_FEB_15.md)**

*   **Phase 1: Silicon Base (Heart & Pulse)**
    1.  [TODO] **GGUF Harvester**: Point vLLM directly to `/usr/share/ollama` blobs (No HF token needed).
    2.  [TODO] **VRAM Heartbeat**: Restore sliding-window GPU throttling (Gem I).

*   **Phase 2: The Soul (High Fidelity Logic)**
    3.  [TODO] **Memory Bridge**: Restore 3-turn context echo for Brain handovers (Gem A).
    4.  [TODO] **Gemma Banter**: Inject native `<start_of_turn>model` pre-cognitive filler (Gem F).
    5.  [TODO] **Hallucination Shunt**: Re-route invalid tool calls to Pinky (Gem D).

*   **Phase 3: Nervous System (Experimental)**
    6.  [TODO] **Silicon Halt**: Verify mid-sentence `vllm.engine.abort()` (Gem B).
    7.  [TODO] **Shadow Dispatch**: Prototype background generation during user typing (Gem J).

## Key Components & Status
