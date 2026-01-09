# Project Status: Acme Lab (Voice-Activated Personal Knowledge Assistant)

**Date:** January 9, 2026
**Current Phase:** Phase 5: The Agentic Facilitator

## Architecture: "The Bicameral Mind" (See [Architecture_Refinement_2026.md](docs/plans/Architecture_Refinement_2026.md))
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
**Goal:** Balance the Right (Flow) and Left (Logic) hemispheres to fix the "Loop of Doom."

*   **[CRITICAL] Bicameral Balance (Fix Loop of Doom):**
    *   Update Pinky's prompt: Prioritize **User Satisfaction (Flow)** over **Code Perfection (Logic)**. Stop nitpicking.
    *   Update Brain's prompt: Assert authority on logic questions to break loops.
*   **[TODO] Vibe Detection (Pinky):**
    *   Pinky must detect `user_sentiment` (e.g., Frustrated, Curious) and write it to the Shared Context.
*   **[TODO] Hemisphere Banter:**
    *   Refine dialogue so Pinky reacts to *complexity/emotion* and Brain reacts to *facts/structure*.

### Phase C: Dreaming & Memory (Next Up)
**Goal:** Implement the "Day/Night" cycle for memory consolidation.

*   **[AUTO] [Diff: 4] Day & Night Collections:**
    *   Split `ArchiveNode` into `short_term_stream` (Right Brain Pile) and `long_term_wisdom` (Left Brain Archive).
*   **[AUTO] [Diff: 5] The Dream Scheduler:**
    *   Implement a "Dreaming Mode" where the Brain wakes up (Idle/Night) to summarize the Stream into Wisdom.
*   **[AUTO] [Diff: 3] Task State Manager:** Pinky tracks "ToDo" lists as short-term context.

## The Freezer (Future Concepts)
See [Future_Concepts.md](docs/plans/Future_Concepts.md):
*   **The Intercom:** Nerve Endings (ESP32).
*   **The Red Phone:** Optic Nerve (Windows Client).
*   **Dreaming Implementation:** The specific prompt engineering for the dream cycle.

## Dev Tools
*   `./run_remote.sh [MODE]`: The primary development tool.
*   `src/test_round_table.py`: Logic Validation (Fast).
*   `src/mic_test.py`: Interactive Voice Client.