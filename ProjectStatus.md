# Project Status: HomeLabAI

**Date:** February 5, 2026
**Current Phase:** Phase 8: Federated Hybrid Cloud (Resilience & RAG)
**Global Status:** [../Portfolio_Dev/00_FEDERATED_STATUS.md](../Portfolio_Dev/00_FEDERATED_STATUS.md)

## 🗺️ Documentation Map
*   **Vision & Architecture:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Acme Lab Model)
*   **Rules of Engagement:** [Protocols.md](docs/Protocols.md) (Demos, Testing, & Heads Down)
*   **AI Master Plan:** [AI_MASTER_PLAN.md](docs/plans/AI_MASTER_PLAN.md) (Long-haul Roadmap)
*   **Tech ROI:** [TECHNOLOGY_ROI.md](docs/plans/TECHNOLOGY_ROI.md) (Optimization Matrix)

## 🗣️ Glossary & Shortcuts
*   **"Co-Pilot Mode"**: Trigger `Interactive Demo Protocol` (uses `DEBUG_PINKY`).
*   **"Heads Down"**: Trigger `Builder Protocol`.
*   **"Fast Loop"**: Trigger `Debug Protocol` (uses `DEBUG_PINKY` + `src/run_tests.sh`).
*   **"The Dream"**: Trigger `src/dream_cycle.py` to consolidate memory.

## ⚠️ Known Traps
*   **Startup Blindness:** `HOSTING` mode takes ~45s. Do not cancel early.
*   **EarNode CUDA Graphs:** MUST be disabled recursively due to CUDA 12.8 mismatch.
*   **Keyboard Handover:** Use **SPACE** to toggle text mode to prevent character eating.
*   **Cloudflare WS:** Requires `aiohttp` for header tolerance (keep-alive).

## Completed Milestones (Session Feb 5)
1.  **RAG Context Bridge [DONE]:**
    *   Fixed bug where RAG context was not forwarded to the Brain node.
2.  **EarNode Recovery [DONE]:**
    *   Resolved `ValueError: not enough values to unpack` by disabling CUDA Graphs recursively.
    *   Verified stability with isolated test `src/test_earnode_isolated.py`.
3.  **Infrastructure Automation [DONE]:**
    *   Automated NVIDIA MPS setup (`src/debug/enable_mps.sh`).
    *   Programmatically provisioned Cloudflare DNS and Access policies.
4.  **Web Intercom Bootstrap [DONE]:**
    *   Scaffolded `intercom.html` and migrated server to `aiohttp`.

## Master Backlog & Roadmap

### Phase A: Infrastructure & Reliability (Next Up)
*   **[TODO] Liger-Kernel:** Integrate fused kernels for 84% VRAM reduction.
*   **[TODO] NVIDIA MPS Persistence:** Move `mps_env.sh` setup to systemd or bashrc.

### Phase C.5: The Client Upgrade
*   **[PLANNED] Web Audio:** Implement MediaStream API for voice input in browser.
*   **[DONE] Web Text:** Basic WebSocket console operational.

## Dev Tools
*   `./src/copilot.sh [MODE]`: Synchronous local integration testing.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/test_earnode_isolated.py`: Isolated mic stability verification.
