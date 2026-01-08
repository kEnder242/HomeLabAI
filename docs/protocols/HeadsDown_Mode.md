# Protocol: Heads Down Mode

**Goal:** Enable long, autonomous work sessions where the Agent executes multiple tasks without User intervention.

## Rules of Engagement

1.  **Time Management**
    *   **Clock Check:** Every 5-10 tool calls, check the current system time.
    *   **Time Box:** Respect the user's defined "Stop Time" (e.g., "Work until 6:00 PM").
    *   **Stop Condition:** If the current time > Stop Time, finish the current atomic task and stop.

2.  **Task Execution (Aggressive Continuity)**
    *   **The Floor, Not the Ceiling:** The initial Sprint Goal is the *minimum*. If completed early, **do not stop**.
    *   **Pull Forward:** Immediately pull tasks from the next Phase (e.g., Phase B -> C) and implement them.
    *   **Bias for Action:** Prefer implementing a "Draft" or "Alpha" version of a future feature over waiting for feedback.
    *   **Queue:** Work sequentially through the `ProjectStatus.md` Backlog.
    *   **Unblocking:** If a task is blocked, **skip it** and move to the next independent task.
    *   **Logging:** Update `ProjectStatus.md` immediately after completing a task.
    *   **Version Control:** Run `git add .` and `git commit` after every atomic task.

3.  **Communication**
    *   **Silence:** Do not output text to the User during the session unless a critical error stops *all* work.
    *   **Memory:** Use `save_memory` to checkpoint major milestones.

4.  **Exit Strategy**
    *   When the session ends (Time or Tasks exhausted):
        *   Write a summary to `docs/plans/WorkSession_<Date>.md`.
        *   Output a concise "Session Complete" message to the User.
