# Session Post-Mortem: The Bicameral Awakening
**Date:** January 9, 2026
**Focus:** Phase B (Bicameral Balance) & Infrastructure Stabilization

## 1. Achievements (What We Built)
*   **The Bicameral Mind:** Formally split the architecture into **Pinky (Right Brain/Facilitator)** and **The Brain (Left Brain/Specialist)**. Updated System Prompts to reflect these personas (Flow vs. Logic).
*   **The Reflex:** Implemented a non-LLM "Reflex" path in `pinky_node.py` to handle critical commands ("Goodbye", "Stop") instantly, bypassing the "Polite LLM" problem.
*   **The Magic Loop Restored:** Rediscovered and documented the `start_server.sh` (Nohup + Tail) pattern for fast, reliable remote execution, rejecting the complex `tmux` approach for standard ops.
*   **Audio Hygiene:** Fixed the "Word Duplication" bug by implementing fuzzy/substring matching in `dedup_utils.py` (though "Phrase Repetition" remains).
*   **Visibility:** Exposed `BRAIN_OUTPUT` events to the client (`mic_test.py`), allowing the user to see the Brain's thoughts even if Pinky hasn't spoken yet.

## 2. Discoveries (What We Learned)
*   **STT Quirk:** Streaming models "rewrite" history (e.g., changing "in" to "In"). Strict string deduplication fails here. Lowercase + Substring matching is required.
*   **The Polite Loop of Doom:** Pinky re-delegates tasks because The Brain politely announces *what he will do* ("I shall investigate...") instead of *doing it*. Pinky interprets this as "Talking, not Working."
*   **Startup Blindness:** `SERVICE` mode takes 45s to load ML models. `start_tmux.sh`'s silence during this phase caused premature cancellations.
*   **Process Management:** `tmux` is excellent for *investigation* (attaching to crashes) but poor for *automation* (hiding PIDs). `nohup` is superior for the "Watcher" pattern.

## 3. Pending Action Items (The Carry-Over)
*   **Refine Delegation:** Tune The Brain to be "Result-Oriented" (Present Tense) to satisfy Pinky's "Action" requirement.
*   **Refine Deduplication:** Handle "Phrase Repetition" where the user pauses and the model outputs two distinct sentences ("In here... In here").
*   **Client Polish:** `mic_test.py` needs better visual separation for Brain vs. Pinky output.
*   **CI/CD:** Formalize `test_shutdown.py` and `test_echo.py` into a single `run_tests.sh` suite.

## 4. Documentation Status
*   **Consolidated:** `Protocols.md` is now the single source of truth.
*   **Mapped:** `ProjectStatus.md` links to all key architecture and backlog docs.
*   **Cleaned:** Obsolete files moved to `src/archive/` and `docs/archive/`.
