# Operational Protocols: Acme Lab

> [!IMPORTANT]
> **IMMUTABILITY RULE:** Protocols in this document can ONLY be added. They must NEVER be refactored, slimmed down, or removed unless explicitly requested by the Lead Engineer.

## BKM-001: The Cold-Start Protocol (Agent Orientation)
**Objective**: Restore the Agent's technical context after a session break or crash.

0.  **Orientation (Bootstrap)**:
    *   Refer to the top-level **[BOOSTRAP.md](../../BOOTSTRAP_v4.3.md)** for the primary navigational hub and global project context.
    *   Consult **[ENGINEERING_PEDIGREE.md](./ENGINEERING_PEDIGREE.md)** for the active architectural laws and design breadcrumbs.
    *   **Inventory Mandate**: Proactively identify existing "wheels" (tests, diagnostic scripts, and tools) in **[DIAGNOSTIC_RUNDOWN.md](./DIAGNOSTIC_RUNDOWN.md)** and **[TOOL_RUNDOWN.md](./TOOL_RUNDOWN.md)** before suggesting or implementing new code.
    *   **State Snapshot**: Read the last 5 entries in **[00_FEDERATED_STATUS.md](../../Portfolio_Dev/00_FEDERATED_STATUS.md)** to identify the current "Front Line" and active sprint.

## BKM-002: The Montana Protocol (Logger Awareness)
**Objective**: Prevent diagnostic blindness when third-party libraries hijack the stream.

*   **Behavior**: If the Lab appears "silent" during a boot or tool-run, do not assume a hang. Third-party modules (NeMo/ChromaDB) frequently hijack the logging handlers.
*   **Verification**: The Agent must prioritize port-polling (e.g., `curl /heartbeat`) over log-scraping when silence is encountered. If silence persists, check for uncommitted logger isolation fixes (FEAT-031).

## BKM-003: Resident Sequencing (Staged Loading)
**Objective**: Maintain awareness of the Lab's staggered cognitive state.

*   **Behavior**: When interacting with the Lab after a fresh boot, the Agent must recognize that nodes (Archive, Pinky, Brain) come online in stages.
*   **Verification**: Wait for the staggered `[READY]` signals in the logs before assuming full capability. Refer to **[FEAT-133]** for the underlying technical law.

## BKM-004: The QQ Protocol (Quick Question)
**Objective**: Prevent state drift and over-investigation during collaborative sessions.

1.  **Shorthand (QQ)**: Treat "QQ: [Question]" as a literal **Quick Question**. Fulfillment consists **exclusively** of providing a direct, concise answer.
2.  **Absolute Halt**: A "QQ" response constitutes 100% completion of the task. Do not proceed to diagnostics, coding, or log-scraping.
3.  **Persistence of Halt**: Informational or retrospective queries (e.g., "Tell me what you did", "Explain that log") do NOT signal a resumption of work. The Agent MUST remain in the **HALT** state until the user provides an explicit execution directive (e.g., "Fix it", "Proceed", "Apply").

## BKM-005: The Design Studio (Greenlight before Silicon Change)
**Objective**: Ensure alignment on naming, architecture, and persona before committing code.

1.  **The Pitch**: Agent summarizes the goal in one sentence.
2.  **The Options**: Agent presents 2-3 implementation paths (e.g., Simple, Robust, Experimental).
3.  **The Naming Ceremony**: Explicit agreement on Nouns (Folders, DB Collections) and Verbs (Tool Names).
4.  **The Contract**: User gives "Greenlight" to a specific path.

## BKM-006: Heads Down / AFK Continuity (The Autonomous Sprint)
**Objective**: Enable deep Agent work cycles during user downtime while maintaining transparency.

1.  **Heads Down Trigger**: Signals the start of an autonomous sprint. The Agent works through the agreed-upon task list (from `ProjectStatus.md` or a specific session goal).
2.  **AFK Hint**: User says "AFK" or "Coffee Break" to signal they are stepping away. The Agent should check for any queued tasks or proceed autonomously.
3.  **High-Fidelity Reasoning**: "Heads Down" does NOT mean "Terse Mode." While the Agent should remain silent (no incremental status updates), it MUST still document its internal reasoning, trade-offs, and "Why" in its tool calls and final reports. High verbosity is the standard for intent preservation.
4.  **Max Momentum**: The Agent must strive to complete as much of the plan as possible. If blocked by hardware or permissions, skip the item and maintain momentum on the next available task.
5.  **Conclusion**: Once the backlog is exhausted or the sprint goal is achieved, provide the verbose **BKM-007** "Heads Up" report.
## BKM-008: The Resilience Ladder (Multi-Tenancy)
**Objective**: Maintain Lab availability without impacting the Lead Engineer's primary tasks (Gaming/Transcoding).

1.  **Tier 1 (High Fidelity)**: Native vLLM using **Gemma 2 2B** Unified Base. Priority: Maximum tool-calling precision.
2.  **Tier 2 (Engine Swap)**: Transition to Ollama. Triggered by vLLM instability or initialization failure.
3.  **Tier 3 (Downshift)**: Transition to **Llama-3.2-1B** or **TinyLlama**. Triggered by moderate GPU pressure from non-AI apps (e.g., Jellyfin).
4.  **Tier 4 (Hibernation)**: Full SIGTERM of AI engines. Triggered by Critical GPU pressure (e.g., 4K Gaming). Context is preserved in the Hub's `recent_interactions` list but inference is paused.

## BKM-009: The Checkpoint Protocol (Save State)
**Objective**: Ensure 100% state persistence for session continuity.
**Trigger**: "Checkpoint", "Save", "Close up shop", or end of a feature sprint.

1.  **State Snapshot**: Wrap the current environment state in a <state_snapshot> XML block (Goal, Constraints, Knowledge, Trail, FS State, Recent Actions, Tasks).
2.  **Status Sync**: Update `ProjectStatus.md` and `Portfolio_Dev/00_FEDERATED_STATUS.md`.
3.  **Memory**: Save key architectural decisions to Long-Term Memory.
4.  **Persistence**: `git add .` and `git commit` with a semantic message. (NEVER push).
5.  **Handover**: Provide a 1-sentence summary of "Where we are" and "What to do next."


## BKM-011: The Safe-Scalpel (Atomic Patcher)
**Objective**: Ensure lint-verified, regression-free code edits.
**Tool**: `HomeLabAI/src/debug/atomic_patcher.py`

1.  **Usage**: Mandatory for ALL code edits in the `HomeLabAI` and `Portfolio_Dev` repositories.
2.  **CLI Mode**: `python3 atomic_patcher.py <file> <desc> <old_text> <new_text>`
3.  **Library Mode**: Import `apply_batch_refinement` for complex, multi-edit tasks.
4.  **Safety**: Automatically runs `ruff` check and rolls back all changes if a lint regression is detected.

## BKM-010: Silicon Co-Pilot (Interactive Mode)
**Objective**: Maintain diagnostic fidelity during live user/agent collaboration.
**Trigger**: "Interactive Demo", "Co-Pilot Mode", or live debugging requests.

1.  **The Test Plan**: Present a clear plan (What to test, expected outcome) before launching.
2.  **Versioning**: Agent MUST bump the system VERSION (in acme_lab.py) if any client/server logic changed to prevent "Old Code" traps.
3.  **Execute (Blocking)**: Agent runs the co-pilot script and WAITS. 
    *   *Timeout*: Tool calls must automatically time out after 300s to prevent Agent lockup.
4.  **Verbal Feedback**: Actively mine logs for user notes (e.g., "Pinky, note that X is broken") received during the session.
5.  **Post-Mortem**: Immediately update `ProjectStatus.md` with findings from both logs and user feedback.


## BKM-012: The Ultimate Patcher (Archive Node)
**Objective**: Enable surgical, diff-based edits with mandatory lint-safety.
**Tool**: `patch_file(filename, diff)` via the Archive Node.

1.  **Format**: Accepts standard **Unified Diffs**.
2.  **Fuzzy Matching**: Indentation-immune and handles line offsets gracefully.
3.  **Safety (Rollback)**: Automatically saves original file state before applying the patch.
4.  **Lint-Gate**: Runs `ruff` check on the patched file. If lint fails, it restores the original content and reports the errors.
5.  **Usage**: Prefer this for any complex, multi-line logic changes where string matching is brittle.

## BKM-013: Pager-Aware Shell Execution (Non-Blocking)
**Objective**: Prevent the Gemini CLI watchdog from terminating processes that are waiting for user input.

1.  **Mandatory Flags**: All `journalctl` and `systemctl` commands MUST include the `--no-pager` flag.
2.  **Environment**: Use `PAGER=cat` for `git log` or other tools that default to a pager.
3.  **Rationale**: In an agentic session, there is no \"User\" to press SPACE. If a command hangs in a pager, it produces no STDOUT, triggering the CLI orchestrator to kill the process as a perceived \"hang.\"

## BKM-014: The Deep-Dive (Show me / Tell me more / Teach me)
**Objective**: Provide high-fidelity technical transfer upon user request.

1.  **Trigger**: Phrases like \"show me\" \"tell me more\", \"teach me\", \"dive into this\", or \"explain the logic\".
2.  **Required Content**:
    *   **Architectural \"Why\"**: The engineering reasoning and impact on the broader Lab ecosystem.
    *   **Structural \"How\"**: Concise code snippets highlighting the critical logic changes.
    *   **Performance Delta**: (If applicable) Perceived or measured change in latency, VRAM, or responsiveness.
3.  **Tone**: Professional, direct, and technical. Avoid conversational chitchat.

## BKM-007: The "Heads Up" Report (High-Fidelity Debrief)
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Verbosity**: The report must be detailed and verbose (reversing minimalist CLI compression).
3.  **Content**:
    *   Summary of all completed items.
    *   Implications: Impact on VRAM, latency, and security.
    *   The "Path Backwards": Rollback steps if the new silicon is unstable.
4.  **Verification**: Re-verify all services (Ollama, vLLM, Intercom) before handing back control.

## BKM-020: High-Fidelity Sprint Documentation (Intent Preservation)
**Objective**: Prevent 'Loss of Intent' during context-window shifts or session restores.
1.  **Task Verbosity**: Tasks must NOT be one-liners. They must include the 'Why' (Rationale), the 'How' (Mechanism), and the 'Proof' (Verification).
2.  **Historical Trace**: Sprints must document the forensic anchors (logs, code fragments) that justify the change.
3.  **No Summarization**: Do not slim down technical requirements for brevity. Detail is the only protection against agentic regression.
