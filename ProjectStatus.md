# Project Status: HomeLabAI

**Date:** January 9, 2026
**Current Phase:** Phase 6: Semantic Wisdom

## 🗺️ Documentation Map
*   **Vision & Architecture:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Acme Lab Model)
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

## Completed Milestones (Session Jan 11)
1.  **Version Unity (v2.0.0):** Server, Client, and Test Suite synchronized. Added strict handshake validation.
2.  **Intercom Client (Alpha):** `intercom.py` implemented with "Spacebar Toggle" for Voice/Text switching.
3.  **Boot Robustness:** `acme_lab.py` patched to abort boot sequence on shutdown signal (Fixes "Zombie Boot").
4.  **CI/CD Hardening:** `run_tests.sh` updated to restart server between tests and enforce handshake.

## Master Backlog & Roadmap

### Phase B: Tuning the Corpus Callosum (Refinement)
*   **[DONE] Audio Deduplication:** Fuzzy matching implemented.
*   **[DONE] Result-Oriented Brain:** Prompt updated to stop future-tense loops.
*   **[DONE] Vibe Check Integration:** Pinky uses `manage_lab` to decide when to exit.

### Phase C: Intelligence & Memory (Active)
*   **[DONE] Tiered Memory:** Split Archive into Stream and Wisdom.
*   **[DONE] Dream Cycle:** Brain autonomously summarizes logs.
*   **[DONE] Memory Retrieval:** Pinky contextually recalls Wisdom during greetings.
*   **[FAILED] Semantic Search Tuning:** Memory Test failed retrieval. Pinky claims no access. Needs prompt tuning.
*   **[TODO] The Librarian:** Bulk ingest 18 years of notes from `~/knowledge_base` into the Archive.

### Phase C.5: The Client Upgrade (In Progress)
*   **[DONE] Type & Talk:** `intercom.py` supports Spacebar Toggle.
*   **[TODO] Edit Logic:** "Oops, I meant..." correction flow (Appends revision, doesn't rewrite DB).
*   **[TODO] Naming:** Select "Acme Lab" themed name.

### Phase D: The Toolkit (Research Assistant)
*   **[TODO] Web Search Tool:** Give Brain access to the outside world.
*   **[TODO] Research Loop:** Pinky Triage -> Brain Plan -> Search -> Summarize -> Download.

### Future Concepts (The Freezer)
*   **Telegram/Web Interface:** Send Pinky a telegram; receive notifications on mobile.
*   **Hardware Intercom:** ESP32 integration.

## Dev Tools
*   `./run_remote.sh [MODE]`: Primary execution.
*   `src/run_tests.sh`: Automated CI/CD.
*   `src/dream_cycle.py`: Memory maintenance.
