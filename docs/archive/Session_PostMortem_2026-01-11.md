# Session Post-Mortem: The Version Trap & Startup Blindness
**Date:** January 11, 2026
**Session:** Integration Testing (Intercom v2)

## 1. The Core Failure: Version Fragmentation
**Observation:** The client (`intercom.py`) was upgraded to `v2.0.0-alpha` while the server (`acme_lab.py`) remained at `v1.0.4`.
**Impact:** The server rejected the connection with `[System]: SYSTEM ALERT: Client outdated`.
**Root Cause:**
*   Lack of a "Release Synchronization" protocol.
*   Components were treated as loose microservices, but the handshake logic enforces strict coupling.

## 2. The "Startup Blindness" Trap (Confirmed)
**Observation:** Manual attempts to start the server were aborted prematurely because logs were silent.
**Reality:** The server takes **~45 seconds** to load the Ear (Nemotron) and Brain (Ollama) models.
**Fix:** A "Zombie Boot" patch was applied to `acme_lab.py` to allow the boot sequence to be aborted immediately upon receiving a shutdown signal, preventing "unstoppable" loading processes.

## 3. Script Execution Contexts
**Observation:** `start_server_fast.sh` failed when run on the remote host because it is designed as a *Local* orchestrator (it calls `ssh`).
**Insight:** Scripts must be explicitly labeled as `[LOCAL]` or `[REMOTE]` in their headers or documentation to prevent execution context errors.

## 4. Remediation Plan (Executed in Heads Down)
1.  **Unified Versioning:** All components bumped to `v2.0.0`.
2.  **Protocol Update:** Added Versioning and Script Context rules to `Protocols.md`.
3.  **Automated Validation:** Updated `test_shutdown.py` to verify the Handshake logic autonomously.

## 5. Heads Down Results (CI/CD Recovery)
**Status:** ✅ Infrastructure Restored | ⚠️ Logic Tuning Needed

*   **CI/CD Fix:** `src/run_tests.sh` was failing because the `MOCK_BRAIN` server auto-shutdown killed the session before the second test could run.
    *   **Fix:** Updated `run_tests.sh` to explicitly restart the server between test cases.
    *   **Result:** The pipeline now runs to completion.
*   **Logic Failure:** The "Memory Integration" test technically failed its assertion.
    *   **Observation:** The infrastructure worked (connected, queried), but Pinky replied "I don't have access to secrets."
    *   **Action:** This is a prompt/RAG tuning issue, added to the Backlog. It does not block infrastructure stability.