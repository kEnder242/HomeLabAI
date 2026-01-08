# Protocol: Integration Testing (Human-in-the-Loop)

**Goal:** Verify end-to-end functionality with the User acting as the client.

## Rules of Engagement

1.  **State the Plan:** Clearly define what the User needs to do (e.g., "Run mic_test.py") and what to expect.
2.  **The Watcher Pattern:**
    *   Deploy and start the server process on the remote host (detached via `tmux` or `nohup`).
    *   **Action:** Execute a blocking `ssh ... "tail -f --pid=$SERVER_PID logs/pinky.log"` command with a generous timeout (e.g., 300s).
    *   **Constraint:** Explicitly tell the User: "I am watching the logs. I will respond when the test completes or times out."
3.  **No Ninja Edits:** Do not modify code while the User is testing.
4.  **Feedback Loop:**
    *   If the test fails, analyze the captured logs immediately.
    *   If the test succeeds, ask for User confirmation before moving to the next task.

## Common Pitfalls
*   **SSH Traps:** Ensure the server process is truly detached before starting the `tail` watch.
*   **Timeouts:** Set the Agent tool timeout > User test duration.
*   **Silence:** If the server is quiet, the Agent might time out. Ensure the server logs "heartbeats" or the User generates events.
