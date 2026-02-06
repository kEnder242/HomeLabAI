# Project Status: HomeLabAI

**Date:** February 5, 2026
**Current Phase:** Phase 8: Federated Hybrid Cloud (Resilience & Web Voice)
**Global Status:** [../Portfolio_Dev/00_FEDERATED_STATUS.md](../Portfolio_Dev/00_FEDERATED_STATUS.md)

## 🗺️ Documentation Map
*   **Vision & Architecture:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md)
*   **AI Master Plan:** [AI_MASTER_PLAN.md](docs/plans/AI_MASTER_PLAN.md) (Synthesized Keep Research)
*   **EarNode Retrospective:** [SESSION_BKM_FEB_05.md](../Portfolio_Dev/SESSION_BKM_FEB_05.md)

## 🗣️ Glossary & Shortcuts
*   **"Co-Pilot Mode"**: Trigger `Interactive Demo Protocol` (uses `DEBUG_PINKY`).
*   **"Heads Down"**: Trigger `Builder Protocol`.
*   **"The Dream"**: Trigger `src/dream_cycle.py` to consolidate memory.

## ⚠️ Known Traps
*   **EarNode CUDA Graphs:** Auto-detected. System self-heals if CUDA 12.8 conflict occurs.
*   **Cache Walls:** Web Intercom requires `intercom_v2.js?v=3.0` to bypass Cloudflare/Browser cache.
*   **Aiohttp Handshake:** Always ensure handlers return the `web.WebSocketResponse` object.

## Completed Milestones (Session Feb 5)
1.  **EarNode Resilience (v2.5.0):**
    *   Implemented recursive graph disabling fallback.
    *   Verified stability with isolated testing.
2.  **Web Voice (v3.0.0):**
    *   Implemented browser-based PCM capture (16kHz mono).
    *   Integrated binary streaming into `aiohttp` server.
    *   Resolved UI/Script synchronization crashes.
3.  **Infrastructure:**
    *   Provisioned `acme.jason-lab.dev` with Access Bypass for Lab IP.

## Master Backlog & Roadmap
*   **[TODO] Liger-Kernel:** Bench-test 80% VRAM reduction.
*   **[TODO] Web Audio Feedback:** Add "Pinky is Speaking" visual cues to UI.
*   **[PLANNED] Year-to-Year Resume:** Re-index archives for 2005-2024 work history.