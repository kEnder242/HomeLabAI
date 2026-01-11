# Operational Protocols

This document defines the rules of engagement for the Agent (AI) and User.

## 0. Critical Concept: Decoupling Command & Observation
**Theory:** In a distributed system, **Command** (launching a process) and **Observation** (watching it) must be separate actions. Traps occur when we treat the remote system as a local synchronous function.
*   **Command:** Launch and disconnect immediately (Fire & Forget) to retain agency.
*   **Observation:** Poll sockets or tail logs *separately*.
*   **Propagation:** Explicitly push code to the edges.

### The Traps (Examples of Failure)
**🛑 The "SSH Hang" Trap (Coupled Command/Observation)**
*   **Trigger:** Using a blocking `tail` command (like in `start_server.sh`) for **HOSTING** mode.
*   **Result:** The server runs forever, so `tail` never exits. The Agent hangs indefinitely.
*   **Fix:** For `HOSTING` (Service) mode, ALWAYS use `run_remote.sh` (Fire-and-forget). Only use `start_server.sh` for `DEBUG` modes that auto-shutdown.

**🛑 The "Startup Blindness" Trap (Passive Observation)**
*   **Trigger:** Assuming the server is dead because logs are silent for 30s.
*   **Reality:** Heavy ML models (Ear/Brain) take **~45 seconds** to load. This is normal.
*   **Fix:** Do not cancel early. Poll the port/socket if unsure, but do not rely on log grepping (buffering delays).

**🛑 The "Windows Deployment" Trap (Passive Propagation)**
*   **Trigger:** Modifying `mic_test.py` locally and expecting the Windows client to update.
*   **Result:** Windows runs old code against a new server. Chaos ensues.
*   **Fix:** You MUST run `./sync_to_windows.sh` to push client changes to the Google Drive bridge.

---

## 1. Interactive Demo Protocol (The "Co-Pilot" Mode)
**Goal:** Allow the User to test the system live while the Agent monitors the logs.
**Context:** Used when verifying a new feature or after a "Heads Down" sprint.

### The Rules
1.  **Agent Drives:** The Agent runs the server command (`./run_remote.sh DEBUG_BRAIN`).
    *   *Note:* `DEBUG_BRAIN` loads the full stack but exits when the client disconnects.
2.  **Client Deploy:** If `mic_test.py` was modified, the Agent MUST run `./sync_to_windows.sh` BEFORE asking the User to connect.
3.  **Hold The Line:** The Agent executes the command (e.g., `tail -f`) and **waits**.
    *   The Agent expects the tool call to timeout or be cancelled by the User. This is NOT a failure; it is the design.
    *   *Agent Thought:* "I am now holding the server open. I will wait here until the User disconnects me."
3.  **Real-Time Monitoring:** The Agent watches the logs for success criteria (e.g., `[PINKY] Hello`).
4.  **The Voice Feedback Loop:**
    *   **Listen to the User:** The Agent acknowledges that during voice demos, the User will speak "Live Feedback".
    *   **Post-Demo Log Analysis:** Immediately after the demo ends, the Agent MUST `cat` the server logs to extract these verbal insights.
    *   **Backlog Integration:** Verberal feedback from logs must be explicitly added to `ProjectStatus.md`.
5.  **Disconnection:** The User signals completion by cancelling the tool call or typing "Stop".
6.  **Post-Action:** Upon disconnection, the Agent immediately asks: "I saw X and Y. Did it behave as expected?"
7.  **Timestamp Check:** The Agent should be aware that `sync_to_windows.sh` may require `mic_test.py` to be updated. Check timestamps if issues arise.

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

## 3. Environment & Traps (Read Before Starting)
*   **Dev Machine:** `~/HomeLabAI` (Source of Truth).
    *   **Documentation:** stored here for Developer Context. **Do NOT sync docs to the runtime server.** They are for *us*, not the machine.
    *   **Code:** Staged here, then deployed.
*   **Acme Lab (Remote):** `jallred@z87-Linux.local:~/AcmeLab` (Runtime Only).
    *   **Role:** Execution environment. Only `src/` and `*.sh` scripts belong here.
*   **SSH Key:** `ssh -i ~/.ssh/id_rsa_wsl ...`.
*   **Sync First:** ALWAYS run `./sync_to_linux.sh` before restarting the server.
*   **Process Management:**
    *   **HOSTING Mode (Daemon):** Use `./run_remote.sh HOSTING`.
        *   *Why?* Uses `nohup` & exits immediately. Safe for long-running services.
    *   **DEBUG Mode (Interactive):** Use `ssh ... bash src/start_server.sh [MODE]`.
        *   *Why?* Uses `tail --pid` to stream logs to your console. Safe ONLY because `DEBUG` modes auto-shutdown on disconnect.
    *   **Deep Debug:** Use `ssh ... bash src/start_server_fast.sh` (Tmux) for persistent sessions you need to re-attach to.
*   **Modes:**
    *   `HOSTING`: **Persistent.** Loads ML models. Stays alive after disconnects. Use for Long-Term Hosting.
    *   `DEBUG_BRAIN`: **Interactive Demo.** Loads Full Stack (Ear+Brain). Shuts down on disconnect. Use for Manual Testing.
    *   `DEBUG_PINKY`: **Fast Boot.** Skips Brain Prime. Shuts down on disconnect. Use for Logic Tests.
    *   `MOCK_BRAIN`: **Fast Boot.** Simulates Brain responses. Shuts down on disconnect. Use for Flow Tests.

---

### Remote Execution Standards (BKM)
**Goal:** Reliability over simplicity.
1.  **Process Management:** **NEVER use `nohup`.** ALWAYS use `tmux` for background services.
    *   *Why?* Tmux provides a persistent handle for logs (`capture-pane`) and lifecycle management (`kill-session`).
2.  **Environment Variables:** Variables do NOT cross SSH boundaries.
    *   *Bad:* `export VAR=1; ssh host "./script"`
    *   *Good:* `ssh host "VAR=1 ./script"`
3.  **Readiness Checks:** Do NOT grep logs to see if a server is ready. Poll the **Port/Socket**.
    *   Logs buffer. Ports open instantly.
4.  **Mocking:** Heavy ML models (Ear, Brain) must be mockable via Env Vars (`DISABLE_EAR=1`) for fast logic testing.

## 4. Testing Protocols

### The "Fast Test Loop" Requirement
**Goal:** Optimize the development feedback loop by eliminating unnecessary waits.
**Rules:**
1.  **Zero Sleep:** Test scripts MUST NOT rely on fixed `sleep` commands for synchronization.
2.  **Smart Connect:** Scripts must poll/retry connections (e.g., `connect_with_retry`) to start immediately upon server readiness.
3.  **Clean Shutdown:** Test scripts are responsible for sending a shutdown signal to the server upon completion, ensuring no zombie processes remain.
4.  **Telemetry:** All test scripts must output total execution time to verify compliance.
5.  **Target Time:** A complete logic validation suite should run in under **10 seconds** total.

### Timeouts & Latency (The "Cognitive Gap")
We distinguish between **Reflex** and **Cognitive** operations. Tests must be tuned accordingly.
*   **Logic Tests (Python/Regex):** Timeout **< 5s**. Fail fast. If it takes longer, the code is broken.
*   **Cognitive Tests (LLM/Inference):** Timeout **> 30s**. Allow for GPU spin-up and token generation.
    *   *Note:* CI/CD should prioritize **MOCK** modes (simulated LLMs) to keep runs fast (<10s). Use Real LLMs only for integration/release checks.

### CI/CD Rule
*   **Mandate:** After completing ANY Phase or Critical Task, run the full automated suite (`test_shutdown.py`, `test_echo.py`) to prevent regressions.
*   **Failure:** If tests fail, do NOT proceed to the next Phase. Fix the regression immediately.

### Validation Plan: Acme Lab "Round Table" Architecture
(Migrated from `docs/plans/protocols/RoundTable_Validation.md`)

#### Phase 1: The Loop (Logic Layer)
**Goal:** Verify the conversational state machine, tool usage, and "Inner Voice" logic.
**Execution Mode:** Autonomous "Coffee Break" (Simulated Input).

*   **Test Case 1.1: The Direct Reply (Baseline)**
    *   **Scenario:** User says "Hello."
    *   **Success:** Debug Stream shows `Pinky Decision: REPLY`.
*   **Test Case 1.2: The Delegation (Handoff)**
    *   **Scenario:** User says "Calculate pi."
    *   **Success:** `DELEGATE` -> `BRAIN_OUT` -> `REPLY`.
*   **Test Case 1.3: The Critique (Multi-Turn Internal Loop)**
    *   **Scenario:** User says "Write bad code."
    *   **Success:** `DELEGATE` -> `BRAIN_OUT` -> `CRITIQUE` -> `BRAIN_OUT` -> `REPLY`.

#### Phase 2: The Interrupt (Physics Layer)
**Goal:** Verify asynchronous "Barge-In" capabilities.

*   **Test Case 2.1: Interrupting "The Thinker"**
    *   **Scenario:** User interrupts Brain generation.
    *   **Success:** Task Cancelled -> Pinky invoked with "User said 'Wait'".
*   **Test Case 2.2: Interrupting "The Speaker"**
    *   **Scenario:** User interrupts Audio Output.
    *   **Success:** Lab sends `stop_audio` command.
