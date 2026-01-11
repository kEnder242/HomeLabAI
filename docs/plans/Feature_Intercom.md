# Feature Plan: The Intercom (Windows Client)

**Goal:** Graduate `mic_test.py` into a production-worthy, lightweight Windows console application.
**Role:** The primary interface for HomeLabAI. "The Clipboard" where you speak or type.

## 1. Core Philosophy
*   **Lightweight:** No heavy GUI frameworks (`textual`, `Qt`). Use standard console IO.
*   **Quality:** Audio fidelity is paramount. Input polling must not degrade the stream.
*   **Native:** Optimized for Windows (using `msvcrt`), but architecture allows for Linux ports later.

## 2. Technical Architecture (Option A: Native Poller)

### The Loop
The application runs on a single `asyncio` event loop with a State Machine pattern.

*   **Dependencies:** `pyaudio`, `websockets`, `msvcrt` (Standard Lib).
*   **Threading:**
    *   **Main Thread:** Asyncio Loop (WebSocket handling, State Logic).
    *   **Audio Thread:** PyAudio callback (managed by C-layer, non-blocking).
    *   **Input Thread:** `sys.stdin.readline` (spawned only during Typing Mode).

### The State Machine

#### State 1: LISTENING (Default)
*   **Visual:** `[🎤 LISTENING] ... (Stream Log)`
*   **Audio:** Stream is `START`.
*   **Input:** Loop checks `msvcrt.kbhit()` every ~100ms.
*   **Trigger:** User presses `SPACE` or `ENTER`.
*   **Action:** `stream.stop_stream()`. Transition to TYPING.

#### State 2: TYPING (Focus Mode)
*   **Visual:** `[📝 TYPING] >> _`
*   **Audio:** Stream is `STOP` (Muted).
*   **Input:** Spawns `await asyncio.to_thread(sys.stdin.readline)`.
    *   *Why Thread?* `readline` blocks the Main Thread. We must keep the WebSocket heartbeat alive while the user thinks.
*   **Trigger:** User presses `ENTER`.
*   **Action:**
    *   Parse Input (Command vs. Chat).
    *   Send JSON to Acme Lab.
    *   Transition to LISTENING.

## 3. Protocol Upgrades
The Client will send structured JSON instead of raw binary audio in specific cases.

*   **Audio Packet:** `(Binary Blob)` (Unchanged).
*   **Text Packet:**
    ```json
    {
        "type": "text_input",
        "content": "Hello world",
        "client_timestamp": 123456789
    }
    ```
*   **Command Packet:**
    ```json
    {
        "type": "command",
        "command": "stop_audio"
    }
    ```

## 4. Roadmap
1.  **Refactor:** Rename `mic_test.py` -> `intercom.py`.
2.  **State Implementation:** Implement the `async` polling loop.
3.  **Input Threading:** Implement the non-blocking `readline` wrapper.
4.  **Server Support:** Ensure `pinky_node.py` handles `type: text_input` correctly (bypassing STT).
