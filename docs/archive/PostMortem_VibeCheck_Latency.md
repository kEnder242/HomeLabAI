# Post-Mortem: "The Vibe Check" Latency & Testing (Jan 9, 2026)

## 1. The Incident
During the implementation of the "Vibe Check" (allowing Pinky to naturally decide when to exit), the CI/CD pipeline failed repeatedly with `TimeoutError`. The system was functional, but the automated tests—tuned for the previous "Reflex" architecture—were too impatient.

## 2. Root Cause Analysis

### A. Architectural Shift (Reflex vs. Cognition)
*   **Old Architecture (Reflex):** The exit command was a simple Regex check (`if "goodbye" in query`). Execution time: <1ms.
*   **New Architecture (Cognition):** The exit command is an LLM Tool Call.
    *   Pinky receives text -> Context Window Construction -> Inference (Mistral 7B) -> Tool Selection (`manage_lab`) -> JSON Parsing -> Execution.
    *   Execution time: ~2-5 seconds (highly dependent on GPU load and prompt complexity).

### B. Test configuration Mismatch
*   `src/test_shutdown.py` had a hardcoded `timeout=10.0` seconds.
*   While 10s seems generous, it included:
    1.  WebSocket Handshake.
    2.  User Query Transmission.
    3.  **LLM Inference (The Bottleneck).**
    4.  Network RTT.
*   When running in `DEBUG_PINKY` mode, the system was performing correctly, but the test gave up just seconds before the answer arrived.

## 3. The Resolution
*   **Action:** Increased `test_shutdown.py` timeout to **30.0 seconds**.
*   **Action:** Updated assertion logic to look for the *dynamic* message content (`Goodnight! Narf!`) rather than a static system string, verifying the LLM was actually in control.

## 4. Recommendations for Future Streamlining

### A. "Cognitive Timeout" Protocol
We must distinguish between **Logic Tests** (Regex/Python) and **Cognitive Tests** (LLM).
*   **Logic Tests:** Timeout < 5s. (Fail fast if Python is broken).
*   **Cognitive Tests:** Timeout > 30s. (Allow for cold starts/inference spikes).

### B. Mocking Strategy
To get our "10s CI/CD" back, we should not be testing Mistral's ability to say "Goodnight" in every run.
*   **Proposed:** Use `MOCK_BRAIN` mode (or a new `MOCK_PINKY` mode) for the CI/CD pipeline where the LLM is replaced by a dummy returning `{"tool": "manage_lab"}` instantly.
*   **Benefit:** Tests architecture logic without incurring GPU penalties.

### C. The "Reflex Layer"
We should re-introduce a "Safety Reflex" layer for *emergency* stops that bypasses the LLM entirely, while keeping the "Social Exit" for the LLM.
*   `SHUTDOWN_PROTOCOL_OVERRIDE` (already exists) -> Instant Kill.
*   "Goodnight" -> Vibe Check -> Polite Exit.
