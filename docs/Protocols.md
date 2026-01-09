# Operational Protocols

This document defines the rules of engagement for the Agent (AI) and User.

## 1. Interactive Demo Protocol (The "Co-Pilot" Mode)
**Goal:** Allow the User to test the system live while the Agent monitors the logs.
**Context:** Used when verifying a new feature or after a "Heads Down" sprint.

### The Rules
1.  **Agent Drives:** The Agent runs the server command (`./run_remote.sh`). The Agent **does not** just output the command and ask the User to copy-paste it.
2.  **Hold The Line:** The Agent executes the command (e.g., `tail -f`) and **waits**.
    *   The Agent expects the tool call to timeout or be cancelled by the User. This is NOT a failure; it is the design.
    *   *Agent Thought:* "I am now holding the server open. I will wait here until the User disconnects me."
3.  **Real-Time Monitoring:** The Agent watches the logs for success criteria (e.g., `[PINKY] Hello`).
4.  **The Voice Feedback Loop:**
    *   **Listen to the User:** The Agent acknowledges that during voice demos, the User will speak "Live Feedback" (e.g., "Pinky is too slow" or "The Brain should stay awake").
    *   **Post-Demo Log Analysis:** Immediately after the demo ends, the Agent MUST `cat` the server logs to extract these verbal insights.
    *   **Backlog Integration:** Verberal feedback from logs must be explicitly added to `ProjectStatus.md` as `[Voice-Derived]` tasks.
5.  **Disconnection:** The User signals completion by cancelling the tool call or typing "Stop".
5.  **Post-Action:** Upon disconnection, the Agent immediately asks: "I saw X and Y. Did it behave as expected?"

---

## 2. Heads Down Protocol (The "Builder" Mode)
**Goal:** Enable long, autonomous work sessions where the Agent executes multiple tasks without User intervention.

### Rules of Engagement
1.  **Aggressive Continuity:**
    *   **The Floor, Not the Ceiling:** The Sprint Goal is the *minimum*. If completed early, **do not stop**.
    *   **Pull Forward:** Immediately implement tasks from the next Phase.
    *   **Bias for Action:** Draft "Alpha" features rather than waiting for feedback.

2.  **Execution Loop:**
    *   **Queue:** Work sequentially through `ProjectStatus.md`.
    *   **Unblocking:** If blocked (e.g., sudo/hardware), **skip** and move to the next task.
    *   **Versioning:** `git commit` after every atomic task.

3.  **Exit Strategy:**
    *   Finish only when the Time Limit is reached or the Backlog is empty.
    *   Provide a summary of all completed items.

---

## 3. Environment Orientation
*   **Dev Machine:** `~/HomeLabAI` (Edit Code Here).
*   **Acme Lab (Remote):** `jallred@z87-Linux.local:~/AcmeLab` (Run Code Here).
*   **Tooling:**
    *   `./run_remote.sh [MODE]`: Syncs and runs the Lab.
    *   `./sync_to_linux.sh`: Syncs code only.

---

## 4. Testing Protocols

### The "Fast Test Loop" Requirement
**Goal:** Optimize the development feedback loop by eliminating unnecessary waits.
**Rules:**
1.  **Zero Sleep:** Test scripts MUST NOT rely on fixed `sleep` commands for synchronization.
2.  **Smart Connect:** Scripts must poll/retry connections (e.g., `connect_with_retry`) to start immediately upon server readiness.
3.  **Clean Shutdown:** Test scripts are responsible for sending a shutdown signal to the server upon completion, ensuring no zombie processes remain.
4.  **Telemetry:** All test scripts must output total execution time to verify compliance.
5.  **Target Time:** A complete logic validation suite should run in under **10 seconds** total.
