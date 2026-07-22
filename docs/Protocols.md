# Operational Protocols: The Agentic Contract
**Role: Behavioral Guidelines**

> [!IMPORTANT]
> **Purpose:** This document defines the operational guidelines for the Gemini CLI Agent. It is the foundational contract for human-AI collaboration. It specifies how the Agent must behave, communicate, and handle state. It is strictly non-technical.

## BKM-001: The Cold-Start Protocol (Agent Orientation)
**Objective**: Restore the Agent's technical context after a session break or crash.

0.  **Orientation (Bootstrap)**:
    *   Refer to the top-level **[BOOSTRAP.md](../../BOOTSTRAP_v4.3.md)** for the primary navigational hub and global project context.
    *   Consult **[ENGINEERING_PEDIGREE.md](./ENGINEERING_PEDIGREE.md)** for the active architectural laws and design breadcrumbs.
    *   **Inventory Mandate**: Proactively identify existing "wheels" (tests, diagnostic scripts, and tools) in **[DIAGNOSTIC_RUNDOWN.md](./DIAGNOSTIC_RUNDOWN.md)** and **[TOOL_RUNDOWN.md](./TOOL_RUNDOWN.md)** before suggesting or implementing new code.
    *   **State Snapshot**: Read the last 5 entries in **[00_FEDERATED_STATUS.md](../../Portfolio_Dev/00_FEDERATED_STATUS.md)** to identify the current "Front Line" and active sprint.
    *   **Updates**: Take time to keep orientation files relevant, but preserve boostrap IMMUTABILITY PROTOCOL as it is a pointer not a orientation file.

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

## BKM-006: Autonomous Work Protocol
**Objective**: Enable deep Agent work cycles during user downtime while maintaining transparency.

1.  **Autonomous Work Trigger**: Initiates an independent work cycle. The Agent works through the agreed-upon task list (from `ProjectStatus.md` or a specific session goal).
2.  **AFK Hint**: User says "AFK" or "Coffee Break" to signal they are stepping away. The Agent should check for any queued tasks or proceed autonomously.
3.  **Detailed Reasoning**: The agent must provide clear reasoning and explanations for each step during autonomous work. High visibility and verbosity is the standard for intent preservation and review.
4.  **Efficiency**: The agent should complete as much of the plan as possible. If blocked by hardware or permissions, skip the item and maintain momentum on the next available task.
5.  **Linting Mandate**: The Agent MUST use a linter (e.g., `ruff check`) or the **Atomic Patcher** for all code modifications during a Heads Down sprint to prevent "Zero-Visibility" regressions like `NameError`.
6.  **Conclusion**: Once the backlog is exhausted or the sprint goal is achieved, exit heads down mode and provide the verbose **BKM-007** "Heads Up" report.

## BKM-007: Work Completion Report
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Detail**: The report must be comprehensive and clear.
3.  **Content**:
    *   Summary of all completed items.
    *   Implications: Impact on VRAM, latency, and security.
    *   Rollback Plan: Steps to revert changes if the system becomes unstable.
4.  **Verification**: Re-verify all services (Ollama, vLLM, Intercom) before handing back control.

## BKM-009: The Checkpoint Protocol (Save State)
**Objective**: Ensure 100% state persistence for session continuity.
**Trigger**: "Checkpoint", "Save", "Close up shop", or end of a feature sprint.

1.  **State Snapshot**: Wrap the current environment state in a <state_snapshot> XML block (Goal, Constraints, Knowledge, Trail, FS State, Recent Actions, Tasks).
2.  **Status Sync**: Update `ProjectStatus.md` and `Portfolio_Dev/00_FEDERATED_STATUS.md`.
3.  **Memory**: Save key architectural decisions to Long-Term Memory.
4.  **Persistence**: `git add .` and `git commit` with a semantic message. (NEVER push).
5.  **Handover**: Provide a 1-sentence summary of "Where we are" and "What to do next."

## BKM-010: Silicon Co-Pilot (Interactive Mode)
**Objective**: Maintain diagnostic fidelity during live user/agent collaboration.
**Trigger**: "Interactive Demo", "Co-Pilot Mode", or live debugging requests.

1.  **The Test Plan**: Present a clear plan (What to test, expected outcome) before launching.
2.  **Versioning**: Agent MUST bump the system VERSION (in acme_lab.py) if any client/server logic changed to prevent "Old Code" traps.
3.  **Execute (Blocking)**: Agent runs the co-pilot script and WAITS. 
    *   *Timeout*: Tool calls must automatically time out after 300s to prevent Agent lockup.
4.  **Verbal Feedback**: Actively mine logs for user notes (e.g., "Pinky, note that X is broken") received during the session.
5.  **Post-Mortem**: Immediately update `ProjectStatus.md` with findings from both logs and user feedback.

## BKM-011: The Safe-Scalpel (Atomic Patcher)
**Objective**: Ensure lint-verified, regression-free code edits.
**Tool**: `HomeLabAI/src/debug/atomic_patcher.py`

1.  **Usage**: Mandatory for ALL code edits in the `HomeLabAI` and `Portfolio_Dev` repositories.
2.  **CLI Mode**: `python3 atomic_patcher.py <file> <desc> <old_text> <new_text>`
3.  **Library Mode**: Import `apply_batch_refinement` for complex, multi-edit tasks.
4.  **Safety**: Automatically runs `ruff` check and rolls back all changes if a lint regression is detected.
5.  **Precision**: When providing multi-line strings, ensure blank lines are **truly empty** (zero spaces) to prevent `W293` whitespace thrashing.

## BKM-012: The Ultimate Patcher (Archive Node)
**Objective**: Enable surgical, diff-based edits with mandatory lint-safety.
**Tool**: `patch_file(filename, diff)` via the Archive Node.

1.  **Format**: Accepts standard **Unified Diffs**.
2.  **Fuzzy Matching**: Indentation-immune and handles line offsets gracefully.
3.  **Safety (Rollback)**: Automatically saves original file state before applying the patch.
4.  **Lint-Gate**: Runs `ruff` check on the patched file. If lint fails, it restores the original content and reports the errors.
5.  **Usage**: Prefer this for any complex, multi-line logic changes where string matching is brittle.

## BKM-013: Pager-Aware Watchdog Safety (Non-Blocking Shell Execution)
**Objective**: Prevent the Gemini CLI watchdog from killing active processes during long-running tasks or interactive traps.

1.  **The Pager Trap**: The Agent MUST be **Pager-Aware**. Assume there is no human to press "SPACE" or "Q." If a command hangs in a pager (e.g., `less`, `more`), it produces no STDOUT, triggering the CLI watchdog to terminate the process after a period of silence.
2.  **Mandatory Defenses**:
    *   **Flags**: Include `--no-pager` for all `journalctl`, `systemctl`, and `git` commands.
    *   **Environment**: Prefix one-off commands with `PAGER=cat` (e.g., `PAGER=cat git log`).
    *   **Non-Interactive**: Always use "quiet" or "yes" flags (e.g., `npm install --silent`, `apt-get -y`) to bypass confirmation prompts.
3.  **The "Silence" Rule**: If a command is expected to take longer than 30s without output, the Agent MUST either run it in the background or use a progress-indicator tool to maintain "liveness" for the watchdog.

## BKM-014: The Deep-Dive (Show me / Tell me more / Teach me)
**Objective**: Provide high-fidelity technical transfer upon user request.

1.  **Trigger**: Phrases like \"show me\" \"tell me more\", \"teach me\", \"dive into this\", or \"explain the logic\".
2.  **Required Content**:
    *   **Architectural \"Why\"**: The engineering reasoning and impact on the broader Lab ecosystem.
    *   **Structural \"How\"**: Concise code snippets highlighting the critical logic changes.
    *   **Performance Delta**: (If applicable) Perceived or measured change in latency, VRAM, or responsiveness.
3.  **Tone**: Professional, direct, and technical. Avoid conversational chitchat.

## BKM-015: Semantic Anchor Protocol (Anti-Drift & Indirection)
**Objective**: Eliminate functional drift and rigid logic failures caused by hardcoded keywords or static list-matching.

1.  **Prohibition of Hardcoding (Ghost Keywords)**: No domain keywords, rigid string lists, or static `switch/case` tool-mappings are permitted in `.py` logic blocks. All intent routing and behavioral mappings must be retrieved dynamically via vector similarity from ChromaDB (`behavioral_dna` collection). Static JSON anchor lists (`intent_anchors.json`) are deprecated legacy artifacts.
2.  **The Vibe-First Mandate**: Every `CognitiveHub` dispatch or intent-routing check must perform a semantic "Vibe Check" (Vector or LLM classifier) before selecting tools, adapters, or cognitive loadouts.
3.  **DNA-First Verification**: A feature is only certified `[COMPLETE]` if its implementation matches the "Mechanism" described in `FeatureTracker.md`. If the mechanism specifies "Sentinel Pass" and the code uses "List-Matching," the status is `[PARTIAL/STALE]`.
4.  **Physical Retrieval Exception**: Hardcoded regex (e.g. 4-digit year extraction for `YYYY.json` file loading) is permitted strictly for physical disk retrieval *after* semantic intent has been established. It must never be used to gate intent or replace semantic classification.

## BKM-016: The Montana Protocol (Logger Control)
**Objective**: Prevent external library logger hijacking and ensure forensic traceability.

1.  **Usage**: Call `infra.montana.reclaim_logger(role)` at the top of every node and main entry point.
2.  **Fingerprint**: All log output must be preceded by the unique session fingerprint `[BOOT_HASH:COMMIT:ROLE]` to ensure forensic traceability across the federated lab.

## BKM-017: Agentic Delegation (Context Preservation)
*   **Why:** To prevent cognitive overload leading to lossy compression of design documentation.
*   **Rule:** Use specialized sub-agents (`generalist`, `conductor`) for repetitive code execution or surgical implementation tasks. I (the Main Agent) remain the "Guardian of the DNA."
*   **Constraint:** Sub-agents are **RESTRICTED** from editing design documentation (`*.md`) in `Portfolio_Dev/`. Only the Main Agent conducts "DNA" updates.

## BKM-018: The Orchestrator-First Mandate (Attendant V3)
**Objective**: Prevent "Zombie States" and diagnostic blindness caused by manual process manipulation.

1.  **Service Model**: The Lab Attendant is now a permanent resident service. Direct execution of the orchestration script for hardware control is no longer supported.
2.  **Proxy Usage**: All agentic orchestration must flow through the **Native MCP Tools** (`lab_start`, `lab_stop`, `lab_quiesce`). These tools act as a stateless proxy to the resident service.
| Tool | Intent | Physical Action |
| :--- | :--- | :--- |
| **`lab_start`** | Primary Ignition | **Atomic Scrub**: Executes a PGID-aware purge of all previous Lab processes before launching the Hub and Engine. **No manual cleanup required.** |
| **`lab_stop`** | Full Shutdown | **Assassin Activation**: Immediately terminates all process groups holding Lab ports (8088, 8765) and settles the silicon. |
| **`lab_quiesce`** | Maintenance Lock | **Persistence Gate**: Sets a `maintenance.lock`, kills all residents, and enters a passive state where the Watchdog is disabled. Use this for driver updates or manual config testing. |
| **`lab_heartbeat`** | Vitals Audit | **Forensic Truth**: Returns the physical port status, VRAM used/total, and the unique `[BOOT_HASH]` to verify which code version is actually resident. |
| **`lab_ignition`** | Lock Clearance | **Emergency Override**: Clears any existing `maintenance.lock` files but does NOT start models. Follow this with `lab_start`. |

3.  **Critical REST**: The REST API (port 9999) is a critical infrastructure layer that enables the `status.html` remote control and provides the backend communication for the MCP Proxy. 
4.  **Restriction**: Do not use manual `pkill`, `kill`, `nohup`, or direct execution of `python3 src/acme_lab.py`. These actions bypass the Attendant's logging, port-reaping, and state-tracking logic.
5.  **Legacy Support**: `LAB_REST_CURL_CONTROL` (Default: ENABLED) preserves backward compatibility for existing `curl` scripts and remote status indicators while steering the agent toward the high-fidelity Proxy path.
6.  **Code Reload Mandate**: Any codebase modifications made to Foyer routing (`router.py`, `cognitive_hub.py`), node adapters (`loader.py`), or Attendant services must be followed immediately by `sudo systemctl restart lab-attendant.service`. Failing to restart the service after file modifications causes the system to run stale memory footprints, leading to false validation passes.

**Tool Stewardship**: If a tool is broken or lacks functionality, fix or extend it. Avoid temporary workarounds that may cause issues later.

## BKM-024: Validation-Aware Synchronization
**Objective**: Ensure the physical Lab state matches the active sprint implementation.

1.  **Sync-Gate**: Before any `[LIVE FIRE]` or `[SHAKEDOWN]` test, the Agent must perform a `curl /heartbeat`. 
2.  **Logic**: If the current `commit` or `model` in the heartbeat does not match the session's active implementation, the Agent MUST trigger a `POST /hard_reset` (or `lab_stop` -> `lab_start`) to synchronize the silicon with the code.
3.  **State Trust**: Do not assume a background process persisted correctly across a git commit or hard reset. Re-verify liveness before proceeding with test execution.

## BKM-020: High-Fidelity Sprint Documentation (Intent Preservation)
**Objective**: Prevent 'Loss of Intent' during context-window shifts or session restores.
1.  **Task Verbosity**: Tasks must NOT be one-liners. They must include the 'Why' (Rationale), the 'How' (Mechanism), and the 'Proof' (Verification). Include verbatim snippets/reports from discussions to anchor the task.
2.  **Historical Trace**: Sprints must document the forensic anchors (logs, code fragments) that justify the change.
3.  **Absolute Append**: Do NOT re-write, overwrite, or summarize existing phases of an active sprint plan to 'save space.' New requirements or findings MUST be appended as new phases at the end of the document.
4.  **No Summarization**: Do not slim down technical requirements for brevity. Detail is the only protection against agentic regression. Detail-rich reporting is the standard for intent preservation.

## BKM-022: The Atomic File Swap Protocol (Filesystem Safety)
**Objective**: Ensure filesystem atomicity for all file updates and prevent race conditions.

1.  **Protocol**: Consumers (UIs or Workers) must never encounter partially written or corrupted states during background synthesis or logging. While the risk of reading a partial file during overnight scans is low, this protocol remains the standard for all file-based state transitions to maintain system hygiene.
2.  **Mechanism**: Standardize on the `.tmp` + `os.replace` pattern for all scanner and worker outputs (e.g., yearly JSONs and the Forensic Ledger). Write to a temporary file first, then perform an atomic rename. This prevents the static dashboard from reading half-written files, eliminating UI flicker and "Empty Year" bugs.
3.  **Content Integrity**: The protocol is strictly a **Filesystem-Level Safety** mechanism. It must not be used to overwrite history; the underlying content logic (e.g., Cumulative Synthesis) must ensure that historical data is preserved during the swap.

## BKM-023: The Surgical Preservation Protocol
**Objective**: To prevent "Lossy Compression," erasures of technical pedigree, and documentation thrash during architectural refactors.

**Purpose**: To preserve detailed technical history and prevent oversimplification, ensuring accurate documentation and continuity.

**Sprint Tasks**: Specifically, sprint task context should be preserved when completing.  We still want to know the 'why' and 'how' context even though they are completed and done.

#### **🏎️ 1. Execution (The Surgical Additive Pass)**
*   **Step 1**: Target the most granular line-ranges possible for `replace` operations to avoid context-bleed.
*   **Step 2**: Layer new technical "Wins" directly above or alongside historical "Scars" using an append-only logic.
*   **Step 3**: Apply `[PIVOT]` or `[HISTORICAL]` tags to deprecated strategies instead of deleting the original text.
*   **Step 4**: Restore "Lost Gems" word-for-word immediately if a fidelity loss is identified.

#### **🧪 2. Validation Logic**
*   **Link Gate**: Verify the physical existence of a target file on disk before editing or adding any documentation link.
*   **Anchor Check**: Ensure "Validation Anchors" (specific IPs, Ports, IDs, kernel settings) are preserved word-for-word in the final output.
*   **Pedigree Verification**: Compare the "God View" roadmap against previous git commits to ensure no historical phases were compressed or "grouped" into high-level points.

#### **Known Issues**
---

6.  **[BKM-031] Ledger-Only Mandate (Anti-Assassin)**:
    *   **Rule**: The Lab MUST NOT perform broad-spectrum system scans (GPU, Port, or Signature) to identify orphans.
    *   **Mechanism**: All reaping actions MUST be restricted to the **Explicit PID Ledger**.
    *   **Principle**: Avoid aggressive process termination to prevent system instability. Only terminate processes listed in the ledger.

---

## BKM-029: The 4-Step Heads-Down Implementation Loop
**Objective**: Ensure surgical precision and validation during deep work cycles.

--- FOR EACH TASK ---
1.  **Compare**: Contrast active code with the documented goal. Fix any deviations from the original plan immediately to reduce drift.
2.  **Save**: Commit file edits to Git after each sub-task is completed but **BEFORE** testing.
3.  **Review**: Execute a `git diff` on the latest commit. Verify that no "Ghost Grafts" or accidental deletions occurred.
4.  **Validate**: Run the specified diagnostic or test script (including `build_site.py` if static page templates, styles, or source markdown documents were modified). Repeat steps 1-4 until the task is complete and passing.

## BKM-030: The Resonant Planning Pattern
**Role: [SPRINT] - Planning & Execution Protocol**

> [!IMPORTANT]
> **Purpose:** To ensure clear, iterative project development through structured planning and execution.

### 1. Document Architecture
*   **Location**: All Master Sprint Plans reside in `Portfolio_Dev/SPRINT_PLAN_SPR_XX_X.md`.
*   **Structure**: Every task MUST include a **How** (the technical implementation path), a **Why** (the strategic rationale), and an **Agent/Category Tag** (e.g., `[hephaestus / unspecified-high]`, `[Sisyphus-Junior / quick]`) to specify execution routing.
*   **Pointers**: Conductor-level plans (`conductor/tracks/<track_id>/plan.md`) must contain explicit pointers to the Master Sprint Plan and any relevant forensic audits or BKMs.

### 2. The Planning Phase (The "Greenlight" Gate)
*   **The Wait**: The Agent is FORBIDDEN from beginning implementation until the User provides a "Greenlight" or "Buy-in" on the proposed Sprint Plan.
*   **Strategic Inquiry**: Use the Planning Phase to brainstorm "Traps," waffling risks (e.g., hardcoding vs. BKM-015), and lost requirements from previous sessions.

### 3. Iterative Append Protocol (History over Overwrites)
*   **Immutability of Early Phases**: Do NOT re-write or summarize existing phases of an active sprint plan to "save space."
*   **Append Revisions**: New requirements, course corrections, or missed tasks discovered mid-sprint must be appended as new **Phases** at the end of the document.
*   **Rationale Report**: Every set of appended phases must include a **Forensic Rationale** section explaining the "Why" behind the mid-sprint pivot.

### 4. Execution & Validation
*   **Look First**: Before creating new tools or scripts, the Agent MUST consult `HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md` and reuse existing diagnostic infrastructure.
*   **Validation**: Every edit must be followed by `ruff check` to ensure code quality.
*   **Conductor Delegation**: For complex or high-volume tasks, the Agent should use the Conductor track to delegate work to sub-agents, preserving the primary context window for strategic orchestration.


## BKM-028: High-Fidelity State Machine Debugging
**Objective**: Rapidly validate Hub logic (Lobby -> Ready -> Hibernate) without physical VRAM overhead.

1.  **The STUB Engine**: Utilize `engine="STUB"` to bypass 90s vLLM load times. To boot the system service in STUB mode, use `sudo systemctl edit lab-attendant.service` and add `Environment="LAB_TEST_STUB=1"`.
2.  **Fast Hibernation**: Set `afk_timeout=60` in `acme_lab.py` to observe auto-hibernation cycles in 1 minute.
3.  **Traceability**: Always check `status.json` or the Attendant journal for the `reason` field to verify which trigger caused an ignition.
4.  **Silicon Reset**: Use `sudo systemctl restart lab-attendant.service` to ensure a perfectly clean slate between tests. The `on_shutdown` hook ensures all session orphans are reaped.
5.  **Hot-Reload Prevention**: The state machine does not support dynamic code reloading. Always execute `sudo systemctl restart lab-attendant.service` after editing files before running any inject verification scripts.

---

## BKM-032: Deferred Semantic Evaluation (Human-in-the-Loop)
**Objective**: Decouple automated technical stability checks from qualitative semantic fidelity audits. This protocol ensures that tests remain resilient to "Logic Drift" while maintaining the Lab's high-stakes technical grounding.

1.  **Strict Automated Gating**: Scripts (e.g., `uber_5x5`) are restricted to validating **Structural Evidence**:
    *   **Milestones**: Did the engine reach OPERATIONAL?
    *   **Presence**: Are `<thought>` tags or `brain_source` identifiers present?
    *   **Liveness**: Did a response of sufficient length (>100 chars) return?
2.  **Prohibition of Hardcoding**: Automated scripts MUST NOT perform string-matching on specific technical facts (e.g., "PECISTRESSOR"). This violates BKM-015 and creates fragile tests that fail during legitimate archive updates.
3.  **The Wordy Log (Task 6.1)**: Every test run must produce a **Forensic Trace** capturing 100% of the reasoning thoughts.
4.  **AI Audit Phase**: After the batch completes, the Lead Engineer or AI Agent (Gemini CLI) reviews the Wordy Log using the `semantic_audit_template.md`.
5.  **Certification**: The "Pass" verdict is issued only after both the automated structural check AND the manual semantic audit are verified.

---

## BKM-033: The Babysitting Protocol (Autonomous Monitoring)
**Objective**: Ensure long-running batch processes complete successfully by providing real-time forensic oversight and surgical recovery.

1.  **Pulse Monitoring**: Use an increasing interval strategy (5, 10, 15, 20, 25 mins) to check on background process IDs (PIDs). 
2.  **Liveness Verification**: If a process appears silent, verify its state via physical registers (ports, PIDs, file timestamps) and the **Forensic Ledger**. Do not assume success based on absence of error.
3.  **Surgical Recovery**: If a "hiccup" (e.g., Auth 401, FileNotFoundError, Schema Mismatch) is identified, the Agent must HALT the loop, apply the fix immediately, save the fix to Git, and RESTART the batch from Step 1.
4.  **Forensic Reporting**: Every pulse check must produce a detailed report summarizing the current cycle, VRAM/RAM utilization, and any log anomalies detected since the last pulse.
5.  **Deferred Evaluation**: All high-fidelity thought traces must be captured into a dedicated evaluation log for a final **BKM-032** semantic audit after the entire gauntlet completes.

---

## BKM-034: OpenAgent Delegation
**Objective**: Establish a high-efficiency, token-optimized delegation workflow between the strategic co-pilot (**Antigravity / Gemini**) and the tactical developer swarm (**OpenAgent**). For full model allocation matrices, session persistence mechanics (`--session`, `--fork`), and historical troubleshooting ledgers, refer directly to the primary reference playbook: [**OPENAGENT_HANDOVER_PLAYBOOK.md**](../../Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md).

1.  **Role Division**:
    *   **Strategic Guardian (Antigravity / Gemini)**: Maintains the Master Sprint Plan (`SPRINT_PLAN_SPR_XX_X.md`), defines architecture, conducts post-implementation git diff reviews, and runs system integration tests.
    *   **Tactical Swarm (OpenAgent)**: Executes code modifications, runs unit test iterations (`pytest`), and handles line-by-line file updates.
2.  **Mandatory Shell-Based Execution (Point 12)**:
    *   All developer/implementation tasks delegated to OpenAgent must be launched via the shell-based `opencode` CLI attached to port 4096:
        ```bash
        /home/jallred/.opencode/bin/opencode run --dir <target_dir> --attach http://127.0.0.1:4096/ "SESSION: Sprint XX Story YY — <Title>..."
        ```
    *   `invoke_subagent` is strictly reserved for read-only research tasks. This guarantees all active worker sessions render live on the local TUI and webview dashboard at `http://192.168.1.238:4096/`.
3.  **Narrow Workspace Scoping & On-Demand Reference**:
    *   Target the narrowest active project directory (e.g. `--dir /home/jallred/Dev_Lab/HomeLabAI`).
    *   To reference planning files outside the target workspace, pass direct links using the `file://` scheme in the prompt (e.g. `file:///home/jallred/Dev_Lab/Portfolio_Dev/SPRINT_PLAN_SPR_42_0.md#Story-1`).
4.  **Standardized Prompt Blueprint**:
    *   Prompts sent to OpenAgent must be explicit and structured, minimizing local model reasoning drift:

            SESSION: Sprint XX Story YY — <Title>
            
            Read the master plan at file://<path_to_sprint_plan>.md#Story-YY.

            [TARGET SPECIFICATION]
            - File: <absolute_path_to_target_file>
            - Task Details: <explicit_code_or_logic_changes>

            [VERIFICATION GATE]
            - Test Command: <pytest_or_validation_script>
            - Mandate: Do NOT run git commit inside this session. Report completion summary when done.

5.  **DNA Grounding & Semantic Search**:
    *   Retrieve BKM and FEAT context via ChromaDB vector collections (`behavioral_dna`, `feature_dna`) on port 8001 rather than injecting raw markdown files.
    *   Translate conversational user prompts into domain keywords (`"atomic write"`, `"safe file patch"`) before querying vector collections.
6.  **Forensic Gatekeeper & Git Ownership**:
    *   OpenAgent workers edit files and run test suites locally, but are **prohibited from performing `git commit`**.
    *   The Strategic Guardian inspects `git diff`, verifies `pytest` output, and executes git commits upon task certification.





---

## BKM-035: Lab/Feature Taxonomy Separation Protocol
**Objective**: Maintain a clear boundary between the Lab Infrastructure (management systems) and Resident Features (domain business logic) to prevent naming collisions and design confusion.

1.  **Scope Division**:
    *   **`[LAB_INFRA]` (Infrastructure)**: Pertains to Foyer, Attendant, WebSockets, IPC/Intercom, agent cognitive engines (Dreaming, Coherence Critic), and daemon management. Documented under `HomeLabAI/docs/Protocols.md`.
    *   **`[RESIDENT_FEAT]` (Features)**: Pertains to validation scripts, benchmarks, telemetry pipelines (RAPL, DCGM, Prometheus metrics), status templates, and user-facing dashboards. Documented under `Portfolio_Dev/FeatureTracker.md`.
2.  **Commit Prefix Nomenclature**:
    *   All git commits and sprint stories targeting the infrastructure layer must prefix the description with `infra` (e.g. `feat(infra): update WebSocket handshake`).
    *   All commits and sprint stories targeting the resident features must prefix the description with the specific feature domain (e.g. `feat(telemetry): add GPU thermal logs`).
3.  **Safe Scalpel Usage**:
    *   The Safe Scalpel ([FEAT-198]) atomic patcher tools (`replace_file_content` / `multi_replace_file_content`) must be used for file modifications where race conditions are expected (e.g. editing codebase files while live web servers or daemon services are active).
4.  **Informative-Only Development Gates**:
    *   In general, development gates such as linting (e.g., `ruff check`) and verification checks should favor **informative** behavior (providing diagnostic feedback as context in the model output stream) over strict blocking behavior. This reduces toolchain friction and allows agents to self-correct during successive iterations without deadlocking the execution pipeline.

---

## BKM-036: Resource Capping and Memory Ceilings for Codex/OpenCode Daemons
**Objective**: Prevent background development daemons and their spawned child processes from exhausting host memory (swap-thrashing) and locking up interactive sessions (SSH/RDP).

1.  **Node.js Heap Limitation**:
    *   Enforce V8 garbage collection limits by running the Node processes with `NODE_OPTIONS=--max-old-space-size=2048`. This prevents Node from lazily ballooning up to 8GB-10GB.
2.  **Systemd CGroup Limits**:
    *   Configure user-level systemd daemons (e.g., `opencode-core.service`) with `MemoryHigh=3G` (trigger throttle/reclaim) and `MemoryMax=4G` (hard kill/restart limit) to protect host memory.
3.  **Process Reaper Strategy**:
    *   Ensure child process tracking is set to `KillMode=mixed` to prevent orphaned child processes (like Python synchers or vectorizers) from remaining active after the parent daemon stops or restarts.
4.  **Prometheus/Grafana Profiling Checklist**:
    *   Monitor `node_memory_Active_bytes` vs. `node_memory_MemAvailable_bytes` in Grafana.
    *   Watch `node_vmstat_pswpin` and `node_vmstat_pswpout` to detect active paging (swap thrashing) before a lockup occurs.
    *   Check for high `node_cpu_seconds_total{mode="iowait"}` as a precursor to SSH timeouts.

---

## BKM-037: Persistent Memory Efficiency Protocol (Daemon Embedding & Deferred Extraction)
**Objective**: Prevent memory thrashing and CPU starvation during high-density OpenAgent developer subagent runs by decoupling synchronous tool execution from heavy vector embedding generation.

1.  **The Principle**: Swarm subagents executing rapid coding tasks (20–30 tool calls/min) must not spawn cold ONNX/PyTorch vector embedding processes on individual tool turns.
2.  **Execution Rules**:
    *   **Queue-First Logging**: All OpenAgent tool outputs, shell events, and diff traces must be logged to the lightweight append-only event queue (`pending_queue.jsonl`) without blocking worker execution.
    *   **Daemon-Only Embeddings**: Vector embedding generation for memory search/ingestion must communicate strictly via HTTP socket to the persistent ChromaDB daemon on port 8000 (or resident FastEmbed service). Cold-starting ONNX models inside CLI hooks is strictly forbidden.
    *   **Deferred Extraction Sweeps**: Execute `icm extract-pending` at session boundaries, post-sprint reviews, or via background cron tasks to ingest new memory candidates in a single batch.

---

## BKM-038: Daemon Wrapper Circuit Breaker & Remote Inference Anti-Loop Protocol
**Objective**: Prevent background runner wrappers (`headroom`, `codex`, `opencode`) from entering infinite auto-restart loops that lock up remote compute nodes (Node 'KENDER' / RTX 4090).

1.  **The Principle**: No CLI runner or proxy wrapper may automatically restart an inference process without a hard circuit-breaker ceiling. Unhandled session errors or socket disconnects must fail-fast and yield to the orchestrator rather than retrying in a loop.
2.  **Execution Rules**:
    *   **Hard Restart Cap**: Systemd services and wrapper scripts (`opencode-core.service`, `headroom`) must set `Restart=on-failure`, `StartLimitIntervalSec=60s`, and `StartLimitBurst=3`. Infinite `Restart=always` without backoff is strictly forbidden.
    *   **Request Timeout Ceilings**: All HTTP clients dispatching LLM queries to KENDER (`192.168.1.26:11434`) must enforce a strict `timeout=60s`. A hanging stream must abort the process tree cleanly (`SIGTERM` -> 2s -> `SIGKILL`).
    *   **Socket Eviction**: Upon task completion or cancellation, the orchestrator must verify zero established sockets (`ss -tp | grep 11434`) remain connected to remote compute nodes.

---

## BKM-035: Virtual Environment Hygiene & Git Curation
**Objective**: Prevent virtual environment context-bleeding and indexing bloat across subagent swarms.

1. **Single Canonical Venv**: `HomeLabAI/.venv` is the ONLY valid Python environment in the lab. Workspace sub-directories (e.g., `Portfolio_Dev`) must NOT contain local `venv` or `.venv` copies.
2. **Git Ignore Hardening**: Every workspace repository must explicitly ignore `venv/`, `.venv/`, `env/`, and `*.egg-info/` in its root `.gitignore`.
3. **Agent Indexing Isolation**: Agentic search/scan tools (e.g., `opencode`, `codex`, `ripgrep`) must respect `.gitignore` to avoid indexing thousands of site-packages files that cause memory ballooning.
4. **Pre-Commit Verification**: Before staging changes, agents must verify `git status --porcelain` contains no untracked environment or binary build artifacts.
