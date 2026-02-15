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

## Active Sprint: Project "Awakening" [v4.8] (Feb 15, 2026)
**Objective: Hemispheric Concurrency & Conversational Physics.**

*   **Accomplishments (Logic Verified)**:
    1.  [DONE] **Unitary Shutdown**: Resolved `aclose` task-mismatch hangs.
    2.  [DONE] **Hemispheric Concurrency**: Parallel Dispatch fires Pinky and Brain simultaneously.
    3.  [DONE] **Strategic Sentinel**: Brain interjects autonomously on technical keywords.
    4.  [DONE] **Barge-In Watchdog**: "Wait, stop" speech successfully cancels active generation.
    5.  [DONE] **Federated Failover**: Dynamic KENDER resolution with local fallback verified.

*   **Pending Verification (Gate 5)**:
    1.  [TODO] **Weight Recovery**: Locate/relink local Gemma 2 2B weights for vLLM.
    2.  [TODO] **Multi-LoRA Silicon Gate**: Verify concurrent adapter residency on 11GB.
    3.  [TODO] **Apollo 11**: Profile full-stack KV cache allocation.

## Key Components & Status
