# Project Status: Voice-Activated Personal Knowledge Assistant

**Date:** January 6, 2026
**Current Phase:** Phase 3.5: Personality Injection (Pinky & Brain)

## Architecture
*   **Gateway (Pinky):** `z87-Linux` (NVIDIA 2080 Ti)
    *   **Voice Engine:** NVIDIA NeMo + Nemotron-0.6b (Streaming).
    *   **Role:** The Enthusiastic Sidekick. Handles STT, RAG lookup, and simple queries.
    *   **Model:** `llama3.1:8b` (Local).
*   **Brain (The Brain):** Windows 11 (NVIDIA 4080 Ti)
    *   **Role:** The Mastermind. Handles complex reasoning and coding.
    *   **Model:** `llama3:latest` (Ollama).
    *   **Trigger:** Invoked when Pinky says `"ASK_BRAIN:"`.

## Completed Milestones
1.  **Data Foundation:** Google Drive synced and mounted.
2.  **Voice Environment:** NeMo installed, Model loaded on Linux GPU.
3.  **Phase 1 (Hearing):** Real-time streaming transcription (Windows Mic -> Linux Server) verified.
4.  **Phase 2 (Thinking):** End-to-End Voice Query -> LLM Response verified.
5.  **Persona Architecture:** 
    *   Implemented "Pinky" vs "Brain" routing in `audio_server.py`.
    *   Defined distinct System Prompts for each role.
    *   Pinky defaults to answering; hands off to Brain for complex tasks.
6.  **Observability:**
    *   **Structured Logging:** `logs/conversation.log` captures `[USER]`, `[PINKY]`, and `[BRAIN]` interactions.
    *   **Live Viewer:** `src/view_logs.py` provides a color-coded real-time transcript.
7.  **Persona Guard Rails:**
    *   Implemented `stop` sequences and `num_predict` limits for Pinky to prevent rambling/hallucination.
8.  **Character Profiles:**
    *   Drafted [Persona Profiles](docs/plans/Persona_Profiles.md) including Pinky's "Idiot Savant" trait.

## Dev Tools
*   `./sync_to_linux.sh`: Deploys code to server.
*   **Debug Strategy:** "The Watcher" (Start detached server -> Tail logs -> User Test -> Server auto-exit).
*   **Research:** [Research & Inspiration](docs/plans/Research_and_Inspiration.md) - Curated list of models, architectures, and ideas.



## Master Backlog & Roadmap







### Phase A: Architecture Refactor (The Foundation)

*   **[DONE] Refactor to MCP:** Split `audio_server.py`. Created `PinkyMCPHost` and `BrainMCPServer`.
*   **[DONE] Unified Tooling:** Replaced `ASK_BRAIN:` string parsing with structured MCP tool calls.
*   **[TODO] [Diff: 1] AGENTS.md:** Create a style guide for The Brain to ensure consistent code generation.







### Phase B: Core Features (The "Pinky" Suite)



*   **[AUTO] [Diff: 3] Pinky Model Manager:** Implement Ollama API tools (`pull`, `list`). Pinky can manage Windows models.



*   **[AUTO] [Diff: 2] God Mode:** Add `call_external_api` tool to Pinky's belt.



*   **[AUTO] [Diff: 4] Live Participation ("War Room"):** Upgrade the logging/viewing system to a proper Event Bus so you can see tool calls live.







### Phase C: Intelligence & Memory



*   **[AUTO] [Diff: 4] Tiered Memory:** Implement Session Summaries and CLaRa integration.



*   **[AUTO] [Diff: 3] Task State Manager:** Pinky tracks "ToDo" lists across sessions.







### Phase D: Hardware & Infrastructure (User Heavy)



*   **[USER] [Diff: 2] Smart Power (WOL):** Configure Windows BIOS/NIC. Test `wakeonlan`.



*   **[USER] [Diff: 3] Secure Remote Access:** VPN/Tailscale setup.



*   **[USER] [Diff: 2] Streaming Awareness:** Script to detect Windows processes.







### Integration Demos (Human-in-the-Loop)



*   **[DEMO] The "Hello" Test:** User says "Hello" -> Verify Pinky skips RAG and answers instantly.



*   **[DEMO] The "Hard Question" Test:** User asks for code -> Verify Pinky hands off to Brain (via Tool Call).



*   **[DEMO] The "Interruption" Test:** User speaks while Brain is thinking -> Verify "Barge-In" stops generation.









