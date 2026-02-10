# Operational Protocols

This document defines the standard operating procedures for the HomeLabAI development cycle.

## 0. Critical Concept: Decoupling Command & Observation
**Theory:** In a distributed system, **Command** (launching a process) and **Observation** (watching it) must be separate actions. Traps occur when we treat the remote system as a local synchronous function.
*   **Command:** Launch and disconnect immediately (Fire & Forget) to retain agency.
*   **Observation:** Poll sockets or tail logs *separately*.
*   **Propagation:** Explicitly push code to the edges.

### The Traps (Examples of Failure)
**🛑 The "SSH Hang" Trap (Coupled Command/Observation)**
*   **Trigger:** Using a blocking `tail` command (like in `start_server.sh`) for **SERVICE_UNATTENDED** mode.
*   **Result:** The server runs forever, so `tail` never exits. The Agent hangs indefinitely.
*   **Fix:** For **SERVICE_UNATTENDED** (Service) mode, ALWAYS use `run_remote.sh` (Fire-and-forget). Only use `start_server.sh` for `DEBUG` modes that auto-shutdown.

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
2.  **Versioning:** Agent MUST bump the system `VERSION` (e.g. to 2.2.0) if any client/server logic changed. This forces the user to sync and prevents "Old Code" traps.
3.  **Local Execution:** Server runs locally (via `copilot.sh`) to avoid SSH password prompts and reduce latency.
4.  **Execute (Blocking):** Agent runs `src/copilot.sh` and **waits**.
    *   *Timeout:* The tool call automatically times out after 300s (5 mins) to prevent Agent lockup.
5.  **User Action:**
    *   **Verify Version:** Run `python src/intercom.py`. Confirm it says `Connected to vX.X.X`. 
    *   **Sync:** If a version mismatch occurs, run `./sync_to_windows.sh` and wait for GDrive.
    *   **Test:** Execute Test Plan.
    *   **Verbal Feedback:** Tell Pinky: *"Pinky, note that [bug description]"*.
    *   **Disconnect (Ctrl+C)** to signal completion.
6.  **Analysis (Post-Mortem):** Agent mines logs for **Verbal Feedback** and findings.

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

## 5. The Checkpoint Protocol (Save State)
**Trigger:** "Checkpoint", "Save", "Close up shop", or end of a feature.
**Goal:** Ensure 100% state persistence so the next Agent can resume immediately.

1.  **Status Update:** Update `ProjectStatus.md`.
    *   Mark completed items `[DONE]`.
    *   Define the **Next Action** clearly.
2.  **Memory:** Save key architectural decisions or user preferences to Long-Term Memory.
3.  **Code:** `git add .` and `git commit` with a semantic message.
4.  **Handover:** Provide a 1-sentence summary of "Where we are" and "What to do next."

---

## 6. The BKM Protocol (Point-of-Failure Reporting)
**Trigger:** "BKM Style", "BKM Report", or end of a deployment/fix.
**Goal:** Deliver high-density, action-oriented documentation modeled after SRE Playbooks and Validation Engineering BKMs.

### The Rules
1.  **Preparation (The "Soil"):** Provide 1-liner installation or environment setup commands (e.g., `pip`, `echo`, `chmod`).
2.  **The Critical Logic (The "Core"):** Distill the code down to the absolute essential lines that make the feature work. No filler.
3.  **Trigger Points (The "Action"):** Provide the exact CLI command or tool call used to execute/validate the work.
4.  **Retrospective (The "Scars"):** Explicitly list mis-steps, bugs found during the process, and the specific fixes applied. This is for learning from the struggle.

### Characteristics
*   **Monospace Preferred:** Use code blocks for all commands and logic.
*   **No Chitchat:** Keep the summaries technical and direct.
*   **Atomic:** Each section should be independent and usable as a reference during a "Point of Failure."

## 7. The BKM-Pointer Summary (Referential Documentation)
**Trigger:** "Update generic document", "Add pointer", or when documenting a specific implementation within a broader architectural file.
**Goal:** Avoid duplication by creating lightweight "signposts" that guide future engineers to a solution pattern without copy-pasting the full playbook.

### The Structure
1.  **GOAL:** A 1-sentence statement of what the feature achieves.
2.  **KEYWORD:** The specific search term, API flag, or variable name that is critical to the solution (e.g., `decision: "access_request"`).
3.  **SCOPE:** Where this applies (Application ID, Account Level, File Path).
4.  **LOGIC:** A condensed summary of the "How".
5.  **PAYLOAD/CONFIG:** The specific JSON snippet, configuration block, or command arguments required.
6.  **AUTH/CONTEXT:** Required permissions or environment state.

---

## 8. Session Scars & Lessons Learned
*This section documents hard-won knowledge from specific development sessions.*

### 8.2 Feb 5, 2026 (Cloudflare & WebSocket Resilience)
*   **The WebSocket Incompatibility Trap:** Standard libraries like Python's `websockets` are strict about HTTP headers. Cloudflare Access injects headers like `Connection: keep-alive` which causes an `InvalidUpgrade` error in strict servers.
    *   **BKM:** Use `aiohttp.web` for WebSocket servers behind Cloudflare. It is more tolerant of proxy-injected headers and allows the handshake to complete where strict libraries fail.
*   **The DNS/Tunnel Gap:** Updating `config.yml` only configures the local daemon. It does not update the public internet.
    *   **BKM:** Always run `cloudflared tunnel route dns <ID> <hostname>` after adding a new ingress rule to bridge the gap between the tunnel and public DNS.
*   **The Zero Trust WebSocket Block:** Browsers cannot establish `wss://` connections if the endpoint redirects to a Cloudflare Access login page.
    *   **BKM:** If an Intercom or API is failing to connect, verify the subdomain isn't behind a "Redirect" policy. Use a "Service Auth" or "Bypass" policy for the specific WebSocket route.
*   **Keyboard Buffer Handover:** Using `msvcrt` to detect mode-switch keys (like SPACE) often eats the first character of the subsequent `stdin.readline`.
    *   **BKM:** Explicitly capture the trigger character and prepend it to the result of the text input stream to preserve word integrity (e.g., "Cool" vs "ool").

---

## 9. The Cold Start Protocol (Session Orientation)
**Trigger:** Start of a new session, new agent, or "Welcome Idea."
**Goal:** Rapidly synchronize the agent's mental model with the current lab state, protocols, and guardrails.

1.  **The Bootloader:** Read the root `README.md`.
2.  **The Now:** Read `Portfolio_Dev/00_FEDERATED_STATUS.md` and `HomeLabAI/ProjectStatus.md`.
3.  **The Rules:** Read `Portfolio_Dev/DEV_LAB_STRATEGY.md` and `HomeLabAI/docs/Protocols.md`.
4.  **The Context Check:**
    *   **Git Guardrail:** Confirm `git push` is restricted.
    *   **Environments:** Locate and acknowledge the two isolated venvs.
    *   **LLMs:** Verify status of Pinky (Linux) and The Brain (Windows).
    *   **Archives:** Identify deprecated plans and archived logs to distinguish "Old" vs "New".
5.  **Grounding Report:** Present a concise summary of findings to the Lead Engineer and wait for alignment.