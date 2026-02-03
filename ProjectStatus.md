# Project Status: HomeLabAI

**Date:** February 3, 2026
**Current Phase:** Phase 8: Federated Hybrid Cloud
**Global Status:** [../Portfolio_Dev/00_FEDERATED_STATUS.md](../Portfolio_Dev/00_FEDERATED_STATUS.md)

## 🗺️ Documentation Map
*   **Vision & Architecture:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Acme Lab Model)
*   **Rules of Engagement:** [Protocols.md](docs/Protocols.md) (Demos, Testing, & Heads Down)
*   **Semantic Caching:** [Semantic_Caching_Strategy.md](docs/plans/Semantic_Caching_Strategy.md) (The Clipboard Protocol)

## 🗣️ Glossary & Shortcuts
*   **"Co-Pilot Mode"**: Trigger `Interactive Demo Protocol` (uses `DEBUG_BRAIN`).
*   **"Heads Down"**: Trigger `Builder Protocol`.
*   **"Fast Loop"**: Trigger `Debug Protocol` (uses `DEBUG_PINKY` + `src/run_tests.sh`).
*   **"The Dream"**: Trigger `src/dream_cycle.py` to consolidate memory.

## ⚠️ Known Traps
*   **Startup Blindness:** `HOSTING` mode takes ~45s. Do not cancel early.
*   **Pytest Timeouts:** `pytest` suites involving ChromaDB fixtures may hang on initialization. Use `src/preflight_check.py` first.
*   **Legacy Intercom:** `src/intercom.py` is DEPRECATED. Use the Web UI (Planned).
*   **SSH Key:** Always use `-i ~/.ssh/id_rsa_wsl`.

## Completed Milestones (Session Feb 3)
1.  **Federated Architecture:**
    *   Established "Clean Room" policy: `HomeLabAI` (PyTorch) vs `Portfolio_Dev` (Lightweight).
    *   Cleaned dependencies.
2.  **The Intercom Pivot (Client Deprecation):**
    *   Deprecated Python Client (`intercom.py`) -> Archived to `src/archive/legacy_intercom/`.
    *   **Goal:** Prepare `acme_lab.py` to serve WebSocket connections for the future Web UI.

## Master Backlog & Roadmap

### Phase A: Infrastructure & Reliability (Next Up)
*   **[TODO] Knowledge Indexing Strategy:** "Latest-on-Top" logic for RAG.
*   **[TODO] The Sandbox:** Implement `conduct_experiment` (Docker-based code execution).

### Phase C.5: The Client Upgrade
*   **[PLANNED] Web Audio:** Implement MediaStream API for voice input in browser.
*   **[TODO] Naming:** Select "Acme Lab" themed name for client.

## Dev Tools
*   `./run_remote.sh [MODE]`: Primary execution.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/dream_cycle.py`: Memory maintenance.

## Dev Tools
*   `./run_remote.sh [MODE]`: Primary execution.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/dream_cycle.py`: Memory maintenance.