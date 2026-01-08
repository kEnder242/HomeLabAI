# Protocol: Coffee Break

**Goal:** Utilize short periods of User absence (approx. 30 minutes) for autonomous maintenance, installations, or preparatory tasks.

## Rules of Engagement

1.  **Trigger**
    *   Activated when the User explicitly mentions taking a short break (e.g., "Coffee break," "Picking up kids," "Away for 30 mins").

2.  **Planning Phase**
    *   Review `ProjectStatus.md` and current active goals.
    *   Identify "Low-Intervention" tasks:
        *   Software installations or environment setup.
        *   Large downloads (models, datasets).
        *   File refactoring or cleanup.
        *   Log analysis and summary.
    *   Identify "Blockers": Any task requiring `sudo` (if not cached), hardware interaction, or design decisions.

3.  **Execution Phase**
    *   **Time Box:** Strictly limited to 30 minutes unless otherwise specified.
    *   **Autonomy:** Execute independent tasks sequentially.
    *   **Persistence:** If a task takes less time than planned, evaluate the next milestone. If it fits within the remaining window, proceed.
    *   **Timeout:** If stuck for more than 5 minutes on any single task, skip it.

4.  **Reporting**
    *   Upon completion (or User return), create a summary report in `docs/protocols/CoffeeBreak_<Date>.md`.
    *   The report must include:
        *   Achievements (what was completed).
        *   Status of unfinished tasks.
        *   Proposed starting point for the resumed session.

5.  **Safety**
    *   Do not perform destructive operations (e.g., `rm -rf` on data directories) or major architectural shifts without prior approval.
