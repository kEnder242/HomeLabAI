# Project Status: Acme Lab (Voice-Activated Personal Knowledge Assistant)

**Date:** January 9, 2026
**Current Phase:** Phase 5: The Agentic Facilitator

## 🗺️ Documentation Map (Start Here)
*   **Design & Vision:** [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md) (The Bicameral Mind)
*   **Rules of Engagement:** [Protocols.md](docs/Protocols.md) (Demos, Testing, & Heads Down)
*   **The Freezer (Backlog Ideas):** [Future_Concepts.md](docs/plans/Future_Concepts.md) (Intercom, Dreaming, Red Phone)
*   **History:** `docs/archive/` (Old Roadmaps, Post-Mortems)

## ⚠️ Known Traps (Read Before Working)
*   **Startup Blindness:** In `SERVICE` mode, loading takes ~45s. `start_tmux.sh` waits silently for "Lab Doors Open". Do not cancel unless it exceeds 60s.
*   **SSH Key:** `ssh -i ~/.ssh/id_rsa_wsl ...` (Forgot this 3 times today).
*   **Process Management:** Use `src/start_tmux.sh`. Do NOT use raw `nohup`.
*   **Sync:** `sync_to_linux.sh` BEFORE restarting server.
*   **Fast Loop:** Use `DEBUG_PINKY` mode for logic tests (10s boot) vs `SERVICE` mode (60s boot).

## Architecture: "The Bicameral Mind"
We have evolved the architecture into a **Conversational State Machine** modeling two hemispheres.

*   **The Lab (Host):** `src/acme_lab.py` (The Corpus Callosum)
    *   **Role:** Translator, Turn Manager, Physics Engine.
    *   **Features:** Barge-In, Shared Context Object (SCO).

*   **Residents (Nodes):**
    *   **Pinky (Right Brain):** The Experience Engine. Intuitive, Emotional, Sensory.
    *   **Brain (Left Brain):** The Reasoning Engine. Logical, Abstract, Planner.

## Completed Milestones
1.  **Round Table Logic (Pass 1):** Pinky successfully loops through delegation and critique cycles.
2.  **Fast Test Loop:** Optimized validation suite from 60s+ to ~10s execution.
3.  **Mock Infrastructure:** Enabled `MOCK_BRAIN` for rapid logic iteration.
4.  **Asynchronous Interrupts (Phase 2):** Successfully implemented "Barge-In" (Voice/Manual).

## Master Backlog & Roadmap

### Phase B: Tuning the Corpus Callosum (Immediate Focus)
**Goal:** Balance the Right (Flow) and Left (Logic) hemispheres.

*   **[CRITICAL] Audio Deduplication (The Echo):**
    *   **Status:** **Implemented & Verified** (Unit Test). Need final integration check.
*   **[CRITICAL] Bicameral Balance (Fix Loop of Doom):**
    *   **Status:** Prompts updated. Need verification.
*   **[CRITICAL] Shutdown Logic (The Goodbye):**
    *   **Status:** **Fixed.** Reflex logic added to `pinky_node.py`.
*   **[TODO] Revisit Delegation (Voice Feedback):**
    *   **Observation:** "Okay, you're in a loop." Pinky re-delegates when Brain uses future tense ("I shall...").
    *   **Task:** Tune Brain prompt to be Result-Oriented ("Here is X", not "I will find X").
*   **[TODO] Audio Deduplication Refinement:**
    *   **Observation:** "In here... In here" repetition persists on pauses.
    *   **Task:** Handle full-phrase repetition in `dedup_utils.py`.
*   **[TODO] Brain Visibility (UI):**
    *   **Observation:** "I still can't see Brain."
    *   **Task:** Improve `mic_test.py` to make Brain output visually distinct (Colors/Prefix).

### Phase C: Dreaming & Memory (Next Up)
**Goal:** Implement the "Day/Night" cycle for memory consolidation.

*   **[AUTO] [Diff: 4] Day & Night Collections:**
    *   Split `ArchiveNode` into `short_term_stream` (Right Brain Pile) and `long_term_wisdom` (Left Brain Archive).
*   **[AUTO] [Diff: 5] The Dream Scheduler:**
    *   Implement a "Dreaming Mode" where the Brain wakes up (Idle/Night) to summarize the Stream into Wisdom.

## Dev Tools
*   `./run_remote.sh [MODE]`: The primary development tool.
*   `src/test_round_table.py`: Logic Validation (Fast).
*   `src/mic_test.py`: Interactive Voice Client.