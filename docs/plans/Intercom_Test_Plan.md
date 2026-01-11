# Test Plan: The Intercom (Windows Client)

**Objective:** Verify the functionality of the new `intercom.py` client on the Windows host.

## Prerequisites
1.  **Server:** Ensure `z87-Linux` is running Acme Lab (`./run_remote.sh HOSTING` or `DEBUG_PINKY`).
2.  **Client Code:** Ensure `G:\My Drive\Notes\HomeLabAIProject\src\intercom.py` exists (Deploy via `sync_to_windows.sh`).
3.  **Python:** Windows environment must have `pyaudio` and `websockets` installed (`pip install pyaudio websockets`).

## Test Cases

### 1. Basic Connectivity
*   **Action:** Run `python intercom.py` in PowerShell/CMD.
*   **Expected:**
    *   Console prints `[CLIENT] Connecting to Intercom...`
    *   Console prints `[ACME LAB]: Ready.`
    *   Green text: `[INFO] Press SPACE to Type...`

### 2. Audio Streaming (The Ear)
*   **Action:** Speak into the microphone ("Hello Pinky").
*   **Expected:**
    *   Console shows `👂 Hearing: Hello Pinky...` (streaming partials).
    *   Console shows `🗣️ [YOU]: Hello Pinky` (final transcript).
    *   Pinky replies via text/TTS.

### 3. The Toggle (Spacebar)
*   **Action:** Press the `SPACE` bar.
*   **Expected:**
    *   Audio stream STOPS (Muted).
    *   UI changes to `📝 [TEXT MODE]`.
    *   Prompt appears: `>> _`.

### 4. Text Input (The Clipboard)
*   **Action:** Type `What is the capital of France?` and hit `ENTER`.
*   **Expected:**
    *   UI prints `📝 [YOU]: What is the capital of France?`.
    *   UI returns to `[CLIENT] Mic Resumed.`
    *   Pinky replies (`[Pinky]: The capital is Paris...`).

### 5. Integration: Barge-In
*   **Action:** While Pinky is speaking (long response), type `Stop` and hit `ENTER`.
*   **Expected:**
    *   Pinky stops talking immediately.
    *   Pinky acknowledges the stop.

## Troubleshooting
*   **Dependencies:** If `pyaudio` fails to install on Windows, use `pipwin install pyaudio` or download the `.whl` file manually.
*   **Key Detection:** If `SPACE` doesn't trigger, ensure the console window has focus. `msvcrt` only works on focused windows.
