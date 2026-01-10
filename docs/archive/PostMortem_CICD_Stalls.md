# Post-Mortem: CI/CD Stalls & Remote Execution (Jan 9, 2026)

## 1. The Incident
During the implementation of "Nervous Tics" and the subsequent test pipeline update, we experienced repeated stalls, timeouts, and "missing file" errors. A simple test run turned into a lengthy debugging session.

## 2. Root Cause Analysis (The "Trips")

### A. The `nohup` Trap (Process Management)
*   **Failure:** `run_remote.sh` used `nohup ... &` to spawn the server.
*   **Why it failed:** `nohup` is "fire and forget." When the SSH session closed, there was no guaranteed handle to the process. Output redirection (`> log`) failed silently in some contexts, leading to "No such file" errors when verifying startup.
*   **The Fix:** **Tmux.** A named tmux session (`acme_fast`) provides a persistent, queryable handle. We can inspect stdout/stderr at any time using `tmux capture-pane`.

### B. Environment Variable Void (SSH Scoping)
*   **Failure:** `DISABLE_EAR=1` was set locally but didn't affect the remote process.
*   **Why it failed:** SSH starts a fresh shell. Local environment variables do not propagate unless explicitly exported in the SSH command string.
*   **The Fix:** Explicit passing: `ssh host "VAR=val ./script"`.

### C. Log Grepping vs. Port Polling (Race Conditions)
*   **Failure:** `run_tests.sh` tried to `grep` a remote log file to confirm readiness.
*   **Why it failed:** File buffering delayed the write. The test script timed out reading a file that hadn't been flushed yet, even though the server was likely ready.
*   **The Fix:** **Connection Retries.** The Python test script itself now handles `connect_with_retry`. If the socket accepts a connection, the server is ready. No log parsing required.

### D. The Indentation Blind Spot
*   **Failure:** `replace` tool was used on nested Python code, causing `IndentationError`.
*   **Why it failed:** LLM "diff" logic is fuzzy with whitespace.
*   **The Fix:** For nested Python edits, use `read_file` to confirm context, or `write_file` (rewrite) to guarantee structure.

## 3. Best Known Methods (BKM) for Future Sessions

1.  **Always use Tmux for Background Services:** Never use `nohup`. If it needs to run while I'm not looking, put it in a session.
2.  **Mock Heavy Dependencies:** CI/CD must be <5s. Use `DISABLE_EAR` and `MOCK_BRAIN` flags to skip GPU initialization.
3.  **Poll Sockets, Not Logs:** Logs lie (buffer). Sockets tell the truth.
4.  **Explicit Env Passing:** Never assume variables cross the SSH boundary.
