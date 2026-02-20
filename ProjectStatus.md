# Home Lab AI: Project Status (Feb 14, 2026)

## Current Core Architecture: v4.1 "Abstracted Silicon"
*   **Orchestration**: Managed via **`lab-attendant.service` (systemd)**.
    *   **Telemetry**: Native **NVML** (pynvml) for millisecond hardware watchdog.
    *   **Resilience Ladder**: 4-Tier hierarchy (vLLM -> Ollama -> Downshift -> Suspend).
    *   **Abstract Tiers**: Model-agnostic S/M/L mapping via `vram_characterization.json`.
*   **The Communication Hub (Corpus Callosum)**:
    *   **Unified Base**: Transitioned to the **Standard Tier (e.g., Llama 3.2 3B)** for the 2080 Ti Unity Pattern.
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
**Current Sprint:** **[Sprint Plan: Unity Stabilization](docs/plans/SPRINT_UNITY_STABILIZATION_FEB_15.md)**

**Status Summary:**
*   **Phase 1 (Silicon Base)**: [COMPLETE] **Standard Tier (e.g., Llama 3.2 3B)** established as the Unified Base. vLLM stabilized at 0.5 utilization.
*   **Phase 2 (The Soul)**: [IN PROGRESS] Strategic Map integrated into Pinky via `peek_strategic_map`.
*   **Phase 3 (Nervous System)**: [IN PROGRESS] Shadow Dispatch prototype integrated into transcription loop.

*Refer to the Current Sprint above for the active verification gauntlet and sub-tasks.*

## Key Components & Status
