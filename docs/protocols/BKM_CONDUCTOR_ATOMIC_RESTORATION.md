# BKM-030: Conductor-Led Atomic Restoration Protocol [v1.0]
**Role:** [BKM] - Safety Protocol for Multi-Agent Task Orchestration
**Objective:** To prevent session loops, context drift, and unverified code regressions by utilizing the Conductor Anchor and the Safe-Scalpel (Atomic Patcher) as mandatory gates.

---

## 🛑 0. The Conductor Anchor (The "Truth" Guard)
Before executing any implementations, the agent MUST establish a versioned plan:
1.  **Anchor Creation**: Save a detailed `.md` plan in the `conductor/` directory.
2.  **Meld Strategy**: The plan must include **What** (objective), **How** (logic snippets), and **Why** (physical/forensic rationale).
3.  **Authority of History**: Plans must be grounded in verified Git history ("Win Recipes"), not speculative flag movement.

## 🏎️ 1. Zero-Discovery Handoff (The "Generalist" Gate)
When delegating to sub-agents (e.g., `generalist`), the primary session must "Pre-Prime" the context:
*   **Path Mapping**: Provide absolute paths to all target files.
*   **Block Identification**: Extract and provide exact line numbers and code blocks for modification.
*   **Logic Pre-Surgical**: Never task a sub-agent with "finding a solution." Provide the solution; task the agent with the **Surgical Application**.

## 🛠️ 2. The Safe-Scalpel Protocol (Atomic Edits)
Full-file rewrites are FORBIDDEN for production-critical logic.
*   **The Tool**: Use `HomeLabAI/src/debug/atomic_patcher.py` (Safe-Scalpel) for all code modifications.
*   **The Gate (Lint)**: Every edit must be followed by `/path/to/venv/bin/ruff check <file> --fix`.
*   **The Check (Diff)**: Execute `git diff` immediately after an edit to ensure no unrelated blocks were erased or incorrectly indented.

## ⛩️ 3. Verification Sequence (The "Gauntlet")
A task is only **COMPLETE** if it clears these four gates in sequence:
1.  **Surgical Pulse**: Code is patched and linted (0 errors).
2.  **Physical Truth**: Verify kernel/hardware state (e.g., `nvidia-smi`, `netstat`, `free -h`).
3.  **Cognitive Pulse**: Execute a direct `curl` or specialized audit script (e.g., `test_hibernation_cycle.py`) to verify functional liveness.
4.  **Forensic Log Audit**: Tail the `server.log` and `vllm_server.log` to confirm no hidden stack traces exist.

## 🤕 4. Scars & Preventive Retrospective
*   **Scar #1 (Session Loop)**: Agent repeated "foyer foyer foyer" without progress. 
    *   *Prevention*: Use the Conductor to "Snap-Back" to the last approved plan state.
*   **Scar #2 (The 120s Blind Wait)**: Engine crashed but the test script waited for a timeout.
    *   *Prevention*: Use the **Forensic Wait** logic (log-tailing) to catch "Traceback" early.
*   **Scar #3 (The Dimension Mismatch)**: Attempted to load 3B adapters on a 1B model.
    *   *Prevention*: Mandate dimension verification against `vram_characterization.json` in the planning phase.

---
## 🏆 The Success Mantra
**"Map the Truth. Patch the Line. Verify the Soul."**
