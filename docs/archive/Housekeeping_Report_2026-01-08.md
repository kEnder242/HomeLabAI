# Housekeeping & Coffee Break Report

**Date:** January 8, 2026
**Target:** Environment Health & "Low Hanging Fruit"

## 1. Critical Fixes (Immediate)
*   **BROKEN START SCRIPT:** `src/start_server.sh` points to `src/audio_server.py`, which **does not exist**. It must be updated to run `src/pinky_mcp_host.py`.
*   **MISSING MODEL:** The user expressed interest in "CLaRa" (Apple CLaRa) for summarization. This model is **not present** in the Windows Ollama library (`curl` check confirmed).
    *   *Recommendation:* Use `llama3.1:8b` (already on Windows) or `mistral:7b` (configured in Pinky) for summarization tasks until a specialized model is pulled.
*   **DEPENDENCY CHECK:** Verify `mcp`, `nemo_toolkit`, and `chromadb` are in a `requirements.txt` (currently manual install).

## 2. Low Hanging Fruit (Stretch Goals)
*   **Memory Integration:** `pinky_mcp_host.py` has `ChromaDB` code inline. This is "tech debt". Moving it to a class `MemoryAgent` is a quick win.
*   **Debug Tooling:** The `view_logs.py` is great, but a `test_audio_injection.py` tool would allow us to "fake" voice input for faster testing without speaking. (Wait, `sim_client.py` might do this? Need to verify).

## 3. Demo Recommendations
*   **Need:** **YES**. We need a "Sanity Check" demo before the Heads Down sprint.
*   **Why:** The file structure confusion (`audio_server.py` missing) suggests the environment might be drifty.
*   **Plan:**
    1.  Fix `start_server.sh`.
    2.  Run `mic_test.py` (or `sim_client.py`) -> `pinky_mcp_host.py`.
    3.  Verify the "Hello" response.
