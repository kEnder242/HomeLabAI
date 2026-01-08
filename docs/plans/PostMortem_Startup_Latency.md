# Post-Mortem: Startup Latency & Client Crash (Jan 8, 2026)

## 1. The Incident: "The Lobby Lag"
Despite implementing a "Lobby" system to open the WebSocket early, the User reported a significant delay (~5-10s) before the connection was actually established or responsive. Additionally, the client script (`mic_test.py`) crashed upon receiving a shutdown signal.

## 2. Technical Root Cause Analysis

### A. Main Loop Blockage (The Server Lag)
*   **Observation:** The WebSocket server was initialized, but the code immediately `await`-ed the resident and equipment loading.
*   **The Problem:** Loading ML models (NeMo/Torch) is a heavy, synchronous CPU/IO task. Even though it was "async", the underlying libraries block the thread.
*   **The Result:** The Python event loop was "frozen" while loading models. It could not process the TCP handshake for new WebSocket clients until the models were done. The "Lobby" was effectively a locked door.

### B. Ungraceful Exit (The Client Crash)
*   **Observation:** `mic_test.py` threw a `SystemExit` exception inside a `TaskGroup`.
*   **The Problem:** Using `sys.exit(0)` inside an `asyncio` task forces an immediate exit of the thread, bypassing the normal cleanup logic of other running tasks (like the PyAudio stream). 
*   **The Result:** Asyncio reported "Task exception was never retrieved" because the task died abruptly while other tasks were still waiting on it.

## 3. The Resolution

### Fix A: Background & Threaded Loading
*   **Action:** Moved the `load_residents_and_equipment` call into a background task (`asyncio.create_task`) so the `boot_sequence` returns immediately to the "Run Forever" state.
*   **Action:** Wrapped the `EarNode` (NeMo) initialization in `asyncio.to_thread`. This moves the CPU-heavy model loading to a separate system thread, keeping the Main Event Loop responsive for instant WebSocket connections.

### Fix B: Async Events for Shutdown
*   **Action:** Replaced `sys.exit(0)` with `asyncio.Event.set()`.
*   **Action:** The `main` loop now waits on this event and performs a structured cleanup (cancelling tasks, closing streams) before exiting the script.

## 4. Lessons Learned
*   **Async != Parallel:** Just because a function is `async` doesn't mean it doesn't block. ML model loading is a classic "Blocking IO" case that requires `to_thread`.
*   **Lobby Integrity:** For a "Lobby" to work, the loop *must* stay free. The "Ding!" should be the *only* thing we wait for.
