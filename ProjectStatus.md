# Project Status: Acme Lab (Voice-Activated Personal Knowledge Assistant)

**Date:** January 8, 2026
**Current Phase:** Phase 4: The Acme Lab Architecture

## Architecture: "The Neural Mesh"
We have transitioned from a monolithic script to an **Event-Driven Mesh** using the **Acme Lab** metaphor.

*   **The Lab (Host):** `src/acme_lab.py`
    *   A neutral event bus. connects Equipment (Ear) to Residents (Nodes).
    *   **Modes:**
        *   `SERVICE`: Lazy loading (Green).
        *   `DEBUG_BRAIN`: Eager loading (Hot).
        *   `DEBUG_PINKY`: Local logic only.

*   **Residents (Nodes):**
    *   **Pinky (`pinky_node.py`):** The Persona. Handles Triage.
    *   **Brain (`brain_node.py`):** The Genius. Handles deep compute (Windows).
    *   **Archives (`archive_node.py`):** The Memory. Handles ChromaDB & Summarization.

## Completed Milestones
1.  **Architecture Design:** Defined "Pinky-as-a-Bus" vs "Pinky-as-a-Node".
2.  **Tooling:** Created `run_remote.sh` for seamless Local -> Remote development loops.
3.  **Environment:** Mapped out `HomeLabAI` (Repo) vs `AcmeLab` (Remote Runtime).

## Master Backlog & Roadmap

### Phase A: Architecture Refactor (The Foundation)
*   **[DONE] Refactor to MCP:** Split `audio_server.py`. Created `PinkyMCPHost` and `BrainMCPServer`.
*   **[DONE] Acme Lab Transition:** Modularized into `acme_lab.py`, `nodes/`, and `equipment/`.
*   **[DONE] [Voice-Derived] Async Boot:** Refactored `AcmeLab.boot_sequence` to open the WebSocket *parallel* to Brain Priming.
*   **[TODO] [Diff: 2] AGENTS.md:** Create a style guide for The Brain.

### Phase B: Core Features (The "Pinky" Suite)
*   **[DONE] [Voice-Derived] Conversational Keep-Alive:** Pinky triggers `brain.wake_up()` on every user turn.
*   **[DONE] [Voice-Derived] Rolling Window Tuning:** Tuned `EarNode` to 1.0s buffer / 0.25s overlap.
*   **[AUTO] [Diff: 3] Pinky Model Manager:** Implement Ollama API tools (`pull`, `list`).

### Phase C: Intelligence & Memory
*   **[AUTO] [Diff: 4] Tiered Memory:**
    *   **Episodic:** ChromaDB raw logs (Done).
    *   **Semantic:** Implement `SemanticMemory` class in `ArchiveNode` to track User Preferences/Facts (Ref: MarkTechPost).
    *   **Summarization:** CLaRa Integration (Apple-7B).
*   **[AUTO] [Diff: 3] Task State Manager:** Pinky tracks "ToDo" lists.

## Dev Tools
*   `./run_remote.sh [MODE]`: The primary development tool.
*   `./sync_to_linux.sh`: Deployment script.