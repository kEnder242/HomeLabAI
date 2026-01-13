# Operational Protocols

This document defines the standard operating procedures for the HomeLabAI development cycle.

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

## 1. The Design Studio Protocol (Brainstorming)
**Trigger:** "Let's brainstorm..." or "Enter Design Mode."
**Goal:** Alignment on Naming, Architecture, and Persona *before* code.

1.  **The Pitch:** Agent summarizes the goal in one sentence.
2.  **The Options:** Agent presents 2-3 implementation paths (e.g., Simple, Robust, Narrative).
3.  **The Naming Ceremony:** Explicit agreement on **Nouns** (Folders, DB Collections) and **Verbs** (Tool Names).
4.  **The Storyboard:** A pseudo-script of the interaction (User -> Pinky -> Brain -> Tool) to verify "Vibe".
5.  **The Contract:** A bulleted implementation spec. User gives "Greenlight".

---

## 2. The Interactive Demo Protocol ("Co-Pilot Mode")
**Goal:** Tight, blocking debug loop where Agent and User collaborate synchronously.

### The Rules
1.  **Align:** Agent presents the Test Plan (What to test, expected outcome).
2.  **Execute (Blocking):** Agent runs `src/copilot.sh` and **waits**.
    *   *Timeout:* The tool call automatically times out after 300s (5 mins) to prevent Agent lockup.
    *   *Visibility:* Agent is blind during execution. Logs are processed *after* the server returns.
3.  **User Action:**
    *   Run `python src/intercom.py`.
    *   Execute Test Plan.
    *   **Disconnect (Ctrl+C)** to signal completion and return control to Agent.
4.  **Analysis (Post-Mortem):**
    *   Agent mines logs for **Verbal Feedback** ("Pinky, note that X is broken") and **Implicit Errors** (Tracebacks).
    *   Agent updates `ProjectStatus.md` immediately with findings.
5.  **Safety Valves:**
    *   **AFK Protection:** If no client connects within 60s, Server auto-terminates.
    *   **Crash Recovery:** If Server crashes, the script returns the traceback immediately.

---

## 3. The Builder Protocol ("Heads Down")
**Goal:** Deep work on complex features without full system restarts.

1.  **State Check:** Verify `ProjectStatus.md` is current.
2.  **Branching (Optional):** If risk is high, create a git branch.
3.  **Test-Driven:** Write the `test_*.py` script *before* the feature code.
4.  **Local Validation:** Run tests locally (`DEBUG_PINKY` mode) first.
5.  **Commit:** Frequent commits after each logical step.

---

## 4. The Debug Protocol ("Fast Loop")
**Goal:** Isolate specific bugs in the Pinky/Orchestrator layer.

1.  **Mode:** Use `DEBUG_PINKY` (No Brain/STT loading time).
2.  **Tool:** Use `src/run_tests.sh` for regression testing.
3.  **Focus:** Logic errors, JSON parsing, Tool selection.

---

## 5. The Exit Protocol ("Close Up Shop")
**Trigger:** End of session.

1.  **Status Update:** Update `ProjectStatus.md` (Active -> Done/Backlog).
2.  **Memory:** Save key architectural decisions to Long-Term Memory.
3.  **Analysis:** Create a `Refactoring_Analysis` doc if technical debt was found.
4.  **Commit:** Final git push.
