# Project Status: Acme Lab (Voice-Activated Personal Knowledge Assistant)

**Date:** January 9, 2026
**Current Phase:** Phase 6: Semantic Wisdom

## 🗺️ Documentation Map
*   **Design & Vision:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Bicameral Mind)
*   **Rules of Engagement:** [Protocols.md](docs/Protocols.md) (Demos, Testing, & Heads Down)
*   **The Freezer:** [Future_Concepts.md](docs/plans/Future_Concepts.md) (Intercom, Red Phone)
*   **Post-Mortems:** `docs/archive/` (Recent: `Session_PostMortem_2026-01-09.md`)

## 🗣️ Glossary & Shortcuts
*   **"Co-Pilot Mode"**: Trigger `Interactive Demo Protocol` (uses `DEBUG_BRAIN`).
*   **"Heads Down"**: Trigger `Builder Protocol`.
*   **"Fast Loop"**: Trigger `Debug Protocol` (uses `DEBUG_PINKY` + `src/run_tests.sh`).
*   **"The Dream"**: Trigger `src/dream_cycle.py` to consolidate memory.

## ⚠️ Known Traps
*   **Startup Blindness:** `HOSTING` mode takes ~45s. Do not cancel early.
*   **Client Outdated:** Run `sync_to_windows.sh` if `mic_test.py` changed.
*   **SSH Key:** Always use `-i ~/.ssh/id_rsa_wsl`.

## Completed Milestones (Session Jan 9)
1.  **CI/CD Infrastructure:** `src/run_tests.sh` is now green and mandatory.
2.  **Audio Fix v2:** `dedup_utils.py` handles phrase repetition.
3.  **Visible Brain:** `mic_test.py` colorized; Brain's "inner thoughts" exposed to user.
4.  **Dream Cycle (Pass 1):** `dream_cycle.py` successfully consolidates raw logs into wisdom.
5.  **Robust Shutdown:** Pinky uses "Reflexes" to ensure the Lab closes on "Goodbye".

## Master Backlog & Roadmap

### Phase B: Tuning the Corpus Callosum (Refinement)
*   **[DONE] Audio Deduplication:** Fuzzy matching implemented.
*   **[DONE] Result-Oriented Brain:** Prompt updated to stop future-tense loops.
*   **[TODO] Vibe Check Integration:** Enhance Pinky to use `sentiment` to modulate Brain's verbosity.

### Phase C: Intelligence & Memory (Active)
*   **[DONE] Tiered Memory:** Split Archive into Stream and Wisdom.
*   **[DONE] Dream Cycle:** Brain autonomously summarizes logs.
*   **[TODO] Memory Retrieval:** Improve Pinky's prompt to use the "Wisdom" collection more effectively during greetings.
*   **[TODO] Semantic Search Tuning:** Adjust `n_results` and thresholds for RAG lookups.

## Dev Tools
*   `./run_remote.sh [MODE]`: Primary execution.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/dream_cycle.py`: Memory maintenance.
