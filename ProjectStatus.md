# Project Status: HomeLabAI

**Date:** January 12, 2026
**Current Phase:** Phase 7: Infrastructure & Polish

## 🗺️ Documentation Map
*   **Vision & Architecture:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Acme Lab Model)
*   **Rules of Engagement:** [Protocols.md](docs/Protocols.md) (Demos, Testing, & Heads Down)
*   **Semantic Caching:** [Semantic_Caching_Strategy.md](docs/plans/Semantic_Caching_Strategy.md) (The Clipboard Protocol)
*   **Post-Mortems:** `docs/archive/`

## 🗣️ Glossary & Shortcuts
*   **"Co-Pilot Mode"**: Trigger `Interactive Demo Protocol` (uses `DEBUG_BRAIN`).
*   **"Heads Down"**: Trigger `Builder Protocol`.
*   **"Fast Loop"**: Trigger `Debug Protocol` (uses `DEBUG_PINKY` + `src/run_tests.sh`).
*   **"The Dream"**: Trigger `src/dream_cycle.py` to consolidate memory.

## ⚠️ Known Traps
*   **Startup Blindness:** `HOSTING` mode takes ~45s. Do not cancel early.
*   **Client Outdated:** Run `sync_to_windows.sh` if `mic_test.py` changed.
*   **SSH Key:** Always use `-i ~/.ssh/id_rsa_wsl`.

## Completed Milestones (Session Jan 12)
1.  **Semantic Caching (The Clipboard Protocol):**
    *   Implemented `semantic_cache` in ChromaDB with adaptive thresholds (0.35 distance).
    *   Added TTL (14 days) and Exclusion Rules (Time/Weather).
    *   Renamed tools to match persona: `consult_clipboard`, `scribble_note`.
2.  **Agency Phase: The Drafting Table:**
    *   Created `~/AcmeLab/drafts/` for Brain-generated documents.
    *   Implemented `write_draft` tool with 'The Editor' (deterministic cleaning).
    *   Added support for specific tool delegation in `acme_lab.py`.
3.  **Persona Alignment:** Pinky now understands "His Notes" (Clipboard), "The Library" (RAG), and "The Drafting Table" (Drafts).

## Master Backlog & Roadmap

### Phase A: Infrastructure & Reliability (Next Up)
*   **[DONE] CI/CD Migration:** Moved to `pytest` with `src/conftest.py` fixtures and `src/preflight_check.py` for priming.
*   **[TODO] Knowledge Indexing Strategy:** "Latest-on-Top" logic for RAG.
*   **[TODO] The Sandbox:** Implement `conduct_experiment` (Docker-based code execution).

### Phase C.5: The Client Upgrade
*   **[DONE] Type & Talk:** `intercom.py` supports Spacebar Toggle.
*   **[TODO] Edit Logic:** "Oops, I meant..." correction flow.
*   **[TODO] Naming:** Select "Acme Lab" themed name for client.

## Dev Tools
*   `./run_remote.sh [MODE]`: Primary execution.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/dream_cycle.py`: Memory maintenance.