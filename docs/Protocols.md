# Operational Protocols

This document defines the standard operating procedures for the HomeLabAI development cycle.

---

## 1. The Design Studio Protocol (Brainstorming)
**Trigger:** "Let's brainstorm..." or "Enter Design Mode."
**Goal:** alignment on Naming, Architecture, and Persona *before* code.

1.  **The Pitch:** Agent summarizes the goal in one sentence.
2.  **The Options:** Agent presents 2-3 implementation paths (e.g., Simple, Robust, Narrative).
3.  **The Naming Ceremony:** Explicit agreement on **Nouns** (Folders, DB Collections) and **Verbs** (Tool Names).
4.  **The Storyboard:** A pseudo-script of the interaction (User -> Pinky -> Brain -> Tool) to verify "Vibe".
5.  **The Contract:** A bulleted implementation spec. User gives "Greenlight".

---

## 2. The Interactive Demo Protocol ("Co-Pilot Mode")
**Goal:** Verify system behavior with live audio/text in a safe, auto-closing environment.

1.  **Deploy:** Run `./sync_to_linux.sh` to push latest code.
2.  **Launch:** Agent runs `./run_remote.sh DEBUG_BRAIN`.
    *   *Note:* Uses `start_server_fast.sh` (Tmux) to prevent SSH hangs.
3.  **Monitor:** Agent tails the remote log.
4.  **Interact:** User speaks/types via Client.
5.  **Feedback:** Agent captures specific "Vibe Checks" or bugs from logs.
6.  **Close:** Client disconnect triggers server shutdown.

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