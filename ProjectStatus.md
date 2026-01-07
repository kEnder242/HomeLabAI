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

## Next Steps
1.  **User Test:** 
    *   Verify Pinky answers simple "Hello" queries locally.
    *   Verify Pinky hands off "Write a Python script" queries to The Brain.
2.  **Refine Prompts:** Tune the personality (more "Narf!", more arrogance) based on test results.
3.  **Audio Return:** Stream generated audio (TTS) back to the Windows client.

## Dev Tools
*   `./sync_to_linux.sh`: Deploys code to server.
*   **Debug Strategy:** "The Watcher" (Start detached server -> Tail logs -> User Test -> Server auto-exit).