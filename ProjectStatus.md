# Project Status: Voice-Activated Personal Knowledge Assistant

**Date:** January 6, 2026
**Current Phase:** Voice Gateway (Phase 2) - **COMPLETED**

## Architecture
*   **Gateway:** `z87-Linux` (NVIDIA 2080 Ti)
    *   **Voice Engine:** NVIDIA NeMo + Nemotron-0.6b (Streaming).
    *   **Data Source:** Google Drive mounted at `~/knowledge_base`.
*   **Brain:** Windows 11 (NVIDIA 4080 Ti)
    *   **Inference:** Ollama.
    *   **Input:** Windows Microphone (Pending Client).

## Completed Milestones
1.  **Data Foundation:** Google Drive synced and mounted.
2.  **Voice Environment:**
    *   `~/VoiceGateway/.venv` created.
    *   `ffmpeg`, `libsndfile1`, `portaudio` installed via `sudo`.
    *   `torch` (CUDA) and `nemo_toolkit[asr]` installed.
3.  **Model Verification:**
    *   `nvidia/nemotron-speech-streaming-en-0.6b` successfully downloaded to `~/.cache/huggingface`.
    *   **Verified:** Model loads onto the RTX 2080 Ti without errors.

## Next Steps (When User Returns)
1.  **Server Code:** Write `audio_server.py` on Linux to accept WebSocket audio streams and feed them to Nemotron.
2.  **Client Code:** Write `mic_client.py` on Windows to capture microphone audio and stream it to the Linux server.
3.  **Live Test:** Speak into Windows mic -> See text on Linux terminal.

## Dev Tools
*   `./sync_to_linux.sh`: Use this locally to push code updates to the server.