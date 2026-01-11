# Session Post-Mortem: The Intercom & The Zombie Hunt
**Date:** January 10, 2026
**Focus:** Phase C.5 (Client Upgrade) & CI/CD Stability

## 1. Achievements (What We Built)
*   **The Intercom (`src/intercom.py`):** Graduated the client from a test script to a robust Windows console application.
    *   **Feature:** "Spacebar Toggle" allows instant switching between Voice (Listening) and Text (Typing).
    *   **Tech:** Used `msvcrt` (Standard Lib) for non-blocking polling, avoiding heavy GUI frameworks (`textual`) or invasive hooks (`keyboard`).
*   **Text-Enabled Brain:** Updated `acme_lab.py` to accept `text_input` packets and prioritize them via "Barge-In" (interrupting ongoing audio tasks).
*   **Memory Injection:** Pinky now receives `RELEVANT MEMORY` (RAG) from the Archive in his system prompt, closing the loop on Phase C.
*   **CI/CD Refactor:** Completely rewrote `run_tests.sh` to be robust, using `nc` (Netcat) for socket polling instead of fragile Python one-liners.

## 2. Discoveries (New vs. Old Knowledge)

### A. The mDNS Trap (Why Static IP?)
*   **Old Knowledge:** `z87-Linux.local` (mDNS) works fine for manual SSH sessions.
*   **The Discovery:** When `run_tests.sh` looped a connection check every 2 seconds, the WSL mDNS resolver choked, returning `Invalid argument` to SSH.
*   **The Fix:** Switched to **Static IP (192.168.1.221)** for CI/CD scripts.
*   **Lesson:** Humans can use mDNS. Scripts looping >1Hz must use IPs.

### B. The Zombie Trap (Tmux Cleanup)
*   **Old Knowledge:** `tmux kill-session` kills the session.
*   **The Discovery:** Tmux sends `SIGHUP` to the shell. If the Python process (`acme_lab.py`) doesn't handle SIGHUP, it dies dirty, leaving its children (`archive_node.py`) as orphaned zombies holding DB locks.
*   **The Fix:** Added `signal.SIGHUP` handler to `acme_lab.py` to trigger the same clean shutdown as `SIGINT`.

### C. ChromaDB: The Ghost Hang
*   **Observation:** CI/CD timed out waiting for the server, even after 80s.
*   **Investigation:** `src/profile_chroma.py` showed ChromaDB loads in **7.79s** (Fast!).
*   **Conclusion:** The timeout wasn't performance; it was a **Deadlock**. The previous "Zombie" process (see above) likely held the `chroma.sqlite3.lock` file, preventing the new test instance from starting.
*   **Lesson:** Process Lifecycle management (clean kills) is critical for stateful DB tests.

### D. Python One-Liners
*   **Failure:** `python -c 'async def...'` is a syntax nightmare in Bash.
*   **The Fix:** Use the right tool. `nc -zv` (Netcat) is superior for socket checking.

## 3. Pending Action Items
*   **Verify Intercom:** User needs to run `intercom.py` on Windows to confirm the `msvcrt` logic feels good.
*   **Verify Memory:** The integration test failed due to the Zombie Lock. We need to run `test_memory_integration.py` on a clean system tomorrow.
*   **Chroma Tuning:** 8s load is good, but `archive_node` is heavy (700MB+). Future optimization might be needed.

## 4. Operational Updates
*   **Protocol:** CI/CD scripts now use **IP Addresses** for robustness.
*   **Protocol:** Server now handles **SIGHUP** for Tmux compatibility.
