# Project Status: Acme Lab (Voice-Activated Personal Knowledge Assistant)

**Date:** January 8, 2026
**Current Phase:** Phase 5: The Agentic Facilitator

## Architecture: "The Round Table"
We have evolved the architecture into a **Conversational State Machine**.
Pinky is now the **Agentic Facilitator**, managing the "Floor" and deciding when to involve the Brain.

*   **The Lab (Host):** `src/acme_lab.py`
    *   **Role:** Turn Manager, Physics Engine (Barge-In), and Connection Broker.
    *   **Modes:** `SERVICE` (Production), `MOCK_BRAIN` (Logic Testing).
    *   **Features:** Fast Boot, Smart Shutdown, Asynchronous Interrupts (Barge-In).

*   **Residents (Nodes):**
    *   **Pinky:** The Facilitator. Uses Tools (`delegate`, `critique`, `reply`) to drive flow.
    *   **Brain:** The Specialist. Pure compute.
    *   **Archives:** The Librarian.

## Completed Milestones
1.  **Round Table Logic (Pass 1):** Pinky successfully loops through delegation and critique cycles.
2.  **Fast Test Loop:** Optimized validation suite from 60s+ to ~10s execution.
3.  **Mock Infrastructure:** Enabled `MOCK_BRAIN` for rapid logic iteration.
4.  **Asynchronous Interrupts (Phase 2):** Successfully implemented "Barge-In" (Voice/Manual) to cancel current tasks.

## Master Backlog & Roadmap

### Phase A: Architecture Refactor (The Foundation)
*   **[DONE] Refactor to MCP:** Split `audio_server.py`. Created `PinkyMCPHost` and `BrainMCPServer`.
*   **[DONE] Acme Lab Transition:** Modularized into `acme_lab.py`, `nodes/`, and `equipment/`.
*   **[DONE] Round Table Logic:** Implemented `process_query` loop and Pinky `facilitate` tool.
*   **[DONE] Fast Test Loop:** Optimized `test_round_table.py` and `mic_test.py`.

### Phase B: Interrupts & Flow (The Physics)
*   **[DONE] Asynchronous Barge-In:** Enable Lab to cancel Brain generation on voice activity.
*   **[TODO] Multi-Mouse Dialogue:** Refine Pinky/Brain banter during handoffs.
*   **[TODO] Facilitator Role:** Expand Pinky's prompt to handle project meta-data.

### Phase C: Intelligence & Memory
*   **[AUTO] [Diff: 4] Tiered Memory:**
    *   **Episodic:** ChromaDB raw logs (Done).
    *   **Semantic:** Implement `SemanticMemory` class in `ArchiveNode`.
    *   **Summarization:** CLaRa Integration (Apple-7B).
*   **[AUTO] [Diff: 3] Task State Manager:** Pinky tracks "ToDo" lists.

## Dev Tools
*   `./run_remote.sh [MODE]`: The primary development tool.
*   `src/test_round_table.py`: Logic Validation (Fast).
*   `src/test_audio_pipeline.py`: Hardware Validation (Fast).
*   `src/test_interrupt.py`: Barge-In Validation (Fast).
*   `src/mic_test.py`: Interactive Client (Robust).