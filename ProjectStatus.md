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
**Source of Truth:** **[Sprint Plan: Unity Stabilization](docs/plans/SPRINT_UNITY_STABILIZATION_FEB_15.md)**

**Status Summary:**
*   **Phase 1 (Silicon Base)**: [IN PROGRESS] Re-pointing vLLM to local blobs.
*   **Phase 2 (The Soul)**: [PENDING] Memory Bridge and English-only catalysts.
*   **Phase 3 (Nervous System)**: [PENDING] VRAM Heartbeat and Shadow Dispatch.

*Refer to the Source of Truth above for the active verification gauntlet and sub-tasks.*

## Key Components & Status
