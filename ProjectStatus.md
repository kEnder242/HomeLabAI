# Home Lab AI: Project Status (Feb 14, 2026)

## Current Core Architecture: v4.1 "Abstracted Silicon"
*   **Orchestration**: Managed via **`lab-attendant.service` (systemd)**.
    *   **Telemetry**: Native **NVML** (pynvml) for millisecond hardware watchdog.
    *   **Resilience Ladder**: 4-Tier hierarchy (vLLM -> Ollama -> Downshift -> Suspend).
    *   **Abstract Tiers**: Model-agnostic S/M/L mapping via `vram_characterization.json`.
*   **The Communication Hub (Corpus Callosum)**:
    *   **Unified Base**: Standardized on **Gemma 2 2B** (MEDIUM) for 2080 Ti efficiency.
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

## Active Sprint: Project "Resurrection" (Feb 14, 2026)
**Objective: Generalize the Mind and Harden for Multi-Tenancy.**

*   **Priority Refinements**:
    1.  [DONE] **Gemma 2 2B Deployment**: Configured as the baseline MEDIUM tier.
    2.  [TODO] **Liger Generalization**: Implement model-aware optimization in `vllm_liger_server.py`.
    3.  [DONE] **Transition Cooldown**: KV Cache purge implemented via `handle_refresh` (Silicon Hygiene).
    4.  [DONE] **Downshift tiering**: S/M/L mapping active in Attendant and Nodes.

*   **Core Tasks**:
    1.  [DONE] **Liger Restoration**: Re-enabled Liger-Kernels for AWQ acceleration.
    2.  [DONE] **NVML Migration**: Replaced `nvidia-smi` with direct NVML bindings.
    3.  [IN PROGRESS] **Amygdala v3 Implementation**: Coding "Contextual Double-Take" and Dissonance logic.
    4.  [TODO] **Multi-user stress test**: Run Jellyfin/Steam during active Intercom session.

## Recent Blockers Resolved
*   **Silence Trap**: Eliminated subprocess hangs via NVML and unbuffered output.
*   **State Thrash**: Resolved via backgrounded hot-swaps and explicit transition modes.
*   **Logic Leak**: Replaced all hardcoded model names with S/M/L abstract tiers.
