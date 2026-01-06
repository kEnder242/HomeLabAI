# Distributed Voice Gateway - Project Plan

**Date:** January 6, 2026
**Goal:** Create a ubiquitous, latency-sensitive Voice Assistant for the Home Lab.

## Architecture Overview

### 1. The Central Gateway (Host: `z87-Linux`)
*   **Hardware:** NVIDIA RTX 2080 Ti
*   **Role:** The "Brain Stem". Handles sensory input/output and immediate processing.
*   **Services:**
    *   **Voice Server:** Likely based on the **Wyoming Protocol** (for native Home Assistant compatibility) or a custom Python WebSocket server.
    *   **STT (Speech-to-Text):** `nvidia/nemotron-speech-streaming` (Goal) or `faster-whisper` (Fallback/Initial).
    *   **TTS (Text-to-Speech):** `piper` (Low Latency) or `OpenVoice` (High Quality).
    *   **RAG Orchestrator:** Intercepts transcribed text, queries the Vector DB (Docker), augments the prompt, and sends to LLM.

### 2. The Intelligence Engine (Host: `Windows 11`)
*   **Hardware:** NVIDIA RTX 4080 Ti
*   **Role:** The "Cortex". Pure reasoning and heavy lifting.
*   **Services:**
    *   **Ollama:** Hosting `llama3`, `mixtral`, or `command-r`.
    *   **Audio Client:** A lightweight Python script to stream Microphone audio to the Gateway and play back received TTS audio.

### 3. The Clients
*   **Mobile:** Home Assistant Companion App (via Wyoming satellite) or custom WebRTC webapp.
*   **IoT:** ESP32-S3 Box (Home Assistant Voice Satellite).

---

## Implementation Roadmap

### Phase 1: Environment & Foundation (z87-Linux)
*   [ ] **Remote Setup:** Establish a robust deployment workflow from WSL -> Linux.
*   [ ] **Dependencies:** Install CUDA toolkit, PyTorch, and audio libraries (`portaudio`, `ffmpeg`) on `z87-Linux`.
*   [ ] **Verify STT:** standalone test of `nemotron` or `faster-whisper` on the 2080 Ti.

### Phase 2: The "Hearing" Prototype
*   [ ] **Network Listener:** Create a simple server on Linux that accepts raw audio chunks.
*   [ ] **Transcriber Loop:** Pipe received audio into the STT engine.
*   [ ] **Windows Client (Basic):** Python script on Windows to record mic and push to Linux.

### Phase 3: The "Thinking" Loop
*   [ ] **Ollama Bridge:** Python logic on Linux to send transcribed text -> Windows Ollama API -> Receive Text.
*   [ ] **Latency Check:** Measure "Time to First Token" (TTFT) from Mic input to LLM output.

### Phase 4: The "Speaking" Prototype
*   [ ] **TTS Deployment:** Set up Piper or OpenVoice on Linux.
*   [ ] **Audio Return:** Stream generated audio back to the Windows client.
*   [ ] **Playback:** Windows client plays audio buffer.

### Phase 5: RAG Integration
*   [ ] **Vector DB:** Ensure the existing Docker embedding service is usable.
*   [ ] **Context Injection:** Modify the "Thinking" loop to query the DB before calling Ollama.

---

## Development Workflow (WSL -> Linux)

Since the Agent (Gemini) runs on WSL, but the code runs on Linux:
1.  **Code Locally:** We create scripts in `~/HomeLabAIProject/src` on WSL.
2.  **Deploy Script:** We use a `sync_to_linux.sh` script to `rsync` code to `z87-Linux`.
3.  **Remote Exec:** We use `ssh jallred@z87-Linux.local "python ..."` to run tests.
4.  **Windows Client:** We run the client script directly on Windows (via PowerShell interop or standard Python for Windows).

## Immediate "To-Dos" for the User
1.  **Windows Python:** Ensure Python is installed on Windows (not WSL) to run the microphone client.
2.  **VS Code Remote:** (Optional) Set up VS Code Remote - SSH to `z87-Linux` for easier manual editing if desired.
