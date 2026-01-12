# Operational Protocol: The "Closing Shop" Exit Strategy

**Goal:** Ensure 100% state persistence, documentation parity, and long-term memory integration before the Agent and User disconnect.

## The Trigger
The protocol is activated when the User says:
*   "Closing up shop."
*   "Save and exit."
*   "Wrap it up for the day."
*   "Goodbye."

## The Multi-Level Archive Checklist

### 1. Level: Documentation (The Paper Trail)
*   **Post-Mortem:** Create/Update a file in `docs/archive/Session_PostMortem_YYYY-MM-DD.md`.
    *   Summarize: What worked, what broke, and any "Gotchas" discovered.
    *   Include: Significant log snippets or tracebacks if relevant.
*   **Backlog:** Update `ProjectStatus.md`.
    *   Move completed items to `[DONE]`.
    *   Identify the **immediate next task** for the next session and mark it `[NEXT]`.

### 2. Level: Git (The Code History)
*   **Review:** Run `git status` and `git diff`.
*   **Commit:** Perform a local `git commit` with a descriptive message summarizing the day's progress.
*   **Handshake:** Inform the user if a `git push` is recommended (but do not perform it autonomously).

### 3. Level: Deployment (Optional/Debug Parity)
*   **Sync:** Run `./sync_to_linux.sh` and `./sync_to_windows.sh` if any debug builds or client-side tests were modified.
*   **Role:** This ensures parity for the next development session but is secondary to code persistence (Git).

### 4. Level: Long-Term Memory (The AI Context)
*   **Fact Extraction:** Identify at least 2 key facts about the User's preferences or the project's evolution.
*   **Memory Tool:** Use `save_memory` to commit these to the Gemini persistent store.

### 5. Level: The Handover (The Final Message)
*   **Summary:** Provide a 3-line final summary to the User.
*   **Prompt:** Confirm that the shop is closed.
