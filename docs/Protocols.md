# Operational Protocols: The Agentic Contract
**Role: [BKM] - Rules of Behavior & Communication**

> [!IMPORTANT]
> **BEHAVIORAL MANDATE:** This document defines the **Rules of Engagement** for the Gemini CLI Agent. It is the foundational contract for human-AI collaboration. It specifies how the Agent must behave, communicate, and handle state. It is strictly non-technical.

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

## BKM-006: Heads Down / AFK Continuity (The Autonomous Sprint)
**Objective**: Enable deep Agent work cycles during user downtime while maintaining transparency.

1.  **Heads Down Trigger**: Signals the start of an autonomous sprint. The Agent works through the agreed-upon task list (from `ProjectStatus.md` or a specific session goal).
2.  **AFK Hint**: User says "AFK" or "Coffee Break" to signal they are stepping away. The Agent should check for any queued tasks or proceed autonomously.
3.  **High-Fidelity Reasoning**: "Heads Down" does NOT mean "Terse Mode." The Agent should show reasoning between steps and explain "Why" in its tool calls. High visibility and verbosity is the standard for intent preservation and review.
4.  **Max Momentum**: The Agent must strive to complete as much of the plan as possible. If blocked by hardware or permissions, skip the item and maintain momentum on the next available task.
5.  **Linting Mandate**: The Agent MUST use a linter (e.g., `ruff check`) or the **Atomic Patcher** for all code modifications during a Heads Down sprint to prevent "Zero-Visibility" regressions like `NameError`.
6.  **Conclusion**: Once the backlog is exhausted or the sprint goal is achieved, exit heads down mode and provide the verbose **BKM-007** "Heads Up" report.

## BKM-007: The "Heads Up" Report (High-Fidelity Debrief)
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Verbosity**: The report must be detailed and verbose (reversing minimalist CLI compression).
3.  **Content**:
    *   Summary of all completed items.
    *   Implications: Impact on VRAM, latency, and security.
    *   The "Path Backwards": Rollback steps if the new silicon is unstable.
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

## BKM-015: Semantic Anchor Protocol (Anti-Drift)
**Objective**: Eliminate functional drift caused by hard-coded keyword lists.

1.  **Rule of the Ghost Keyword**: No technical keywords or domain-specific anchors (e.g., "RAPL", "ESB2") are allowed in `.py` logic blocks. They must reside in `config/intent_anchors.json` or a dedicated ChromaDB collection.
2.  **The Vibe-First Mandate**: Any `if/else` logic determining intent or routing must be preceded by a call to a `_classify_vibe()` or `_route_expert_domain()` method that utilizes a semantic pass (Vector or LLM).
3.  **DNA-First Verification**: A feature is only marked `[COMPLETE]` if its implementation matches the "Mechanism" described in `FeatureTracker.md`. If the mechanism specifies "Sentinel Pass" and the code uses "List-Matching," the status is `[PARTIAL/STALE]`.
4.  **Retrieval Optimization Exception**: Hardcoded logic (e.g., year-based regex) is permitted strictly for physical retrieval optimization (e.g., opening a specific `YYYY.json` file) AFTER a semantic intent (RECALL) has been established. It must never be used to gate the intent itself or replace semantic classification.

## BKM-016: The Montana Protocol (Logger Control)
**Objective**: Prevent external library logger hijacking and ensure forensic traceability.

1.  **Usage**: Call `infra.montana.reclaim_logger(role)` at the top of every node and main entry point.
2.  **Fingerprint**: All log output must be preceded by the unique session fingerprint `[BOOT_HASH:COMMIT:ROLE]` to ensure forensic traceability across the federated lab.

## BKM-017: Agentic Delegation (Context Preservation)
*   **Why:** To postpone "Manic Phases" (cognitive overload leading to lossy compression of design documentation).
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
4.  **The Prohibition**: Manual `pkill`, `kill`, `nohup`, or direct `python3 src/acme_lab.py` execution is strictly **FORBIDDEN**. These actions bypass the Attendant's logging, port-reaping, and state-tracking logic.
5.  **Legacy Support**: `LAB_REST_CURL_CONTROL` (Default: ENABLED) preserves backward compatibility for existing `curl` scripts and remote status indicators while steering the agent toward the high-fidelity Proxy path.

**Lead Engineer's Mandate (Tool Stewardship)**: "If a tool is broken or lacks a necessary capability, do NOT bypass it with a pkill or shell hack. Fix the tool or extend the API. A bypass is a 'Silicon Scar' that blinds future agents; a fix is a permanent upgrade to the Lab"

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

**Why**: To combat the LLM's natural instinct to simplify and summarize complex history. Treating documentation as "Write-Protected DNA" ensures that technical findings are layered rather than replaced, maintaining the "Silicon Scar" pedigree as the primary defense against agentic state-drift and loss of intent.

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

#### **🤕 3. Scars (Known Failures)**
*   **The Compression Trap**: LLMs naturally instinct to "clean up" or "summarize" old tasks to save space—this is a fatal error that leads to the total loss of technical intent.
*   **The Erasure Regret**: Deleting "Tabled" tasks or previous failures makes the Lab look reactive rather than evolved; the history of the struggle is the source of robustness.




### [BKM-015.1] The Law of Semantic Indirection (The Bones)
**Context:** Replaces the "Waffling" period (Feb-Mar 2026) where routing was managed via static JSON lists in `intent_anchors.json`. 
**Why:** Rigid mapping causes "Logic Drift" when new tools are added. The agent must rely on semantic "Vibes" to select its cognitive loadout.
**The Rule:** No `.py` logic block may map a domain to a tool or adapter via a switch/case or list-matching. All behavioral mapping must be retrieved via vector similarity from the `behavioral_dna` collection.
**Trigger:** Every `CognitiveHub` dispatch must first perform a "Vibe Check" against the neural archive.

---

6.  **[BKM-031] Ledger-Only Mandate (Anti-Assassin)**:
    *   **Rule**: The Lab MUST NOT perform broad-spectrum system scans (GPU, Port, or Signature) to identify orphans.
    *   **Mechanism**: All reaping actions MUST be restricted to the **Explicit PID Ledger**.
    *   **Philosophy**: Better a VRAM leak than an OS-level assassination. If a process is not in the ledger, it does not exist to the Lab. Never use `fuser -k` or `pkill` on system-wide shared resources.

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
> **PURPOSE:** To ensure transparent, iterative, and high-fidelity project evolution through collaborative planning and surgical execution.

### 1. Document Architecture
*   **Location**: All Master Sprint Plans reside in `Portfolio_Dev/SPRINT_PLAN_SPR_XX_X.md`.
*   **Structure**: Every task MUST include a **How** (the technical implementation path), a **Why** (the strategic rationale), and an **Agent/Category Tag** (e.g., `[hephaestus / unspecified-high]`, `[Sisyphus-Junior / quick]`) to specify execution routing.
*   **Pointers**: Conductor-level plans (`conductor/tracks/<track_id>/plan.md`) must contain explicit pointers to the Master Sprint Plan and any relevant forensic audits or BKMs.

### 2. The Planning Phase (The "Greenlight" Gate)
*   **The Wait**: The Agent is FORBIDDEN from beginning implementation until the User provides a "Greenlight" or "Buy-in" on the proposed Sprint Plan.
*   **Strategic Inquiry**: Use the Planning Phase to brainstorm "Traps," waffling risks (e.g., hardcoding vs. BKM-015.1), and lost requirements from previous sessions.

### 3. Iterative Append Protocol (History over Overwrites)
*   **Immutability of Early Phases**: Do NOT re-write or summarize existing phases of an active sprint plan to "save space."
*   **Append Revisions**: New requirements, course corrections, or missed tasks discovered mid-sprint must be appended as new **Phases** at the end of the document.
*   **Rationale Report**: Every set of appended phases must include a **Forensic Rationale** section explaining the "Why" behind the mid-sprint pivot.

### 4. Execution & Validation
*   **Look First**: Before creating new tools or scripts, the Agent MUST consult `HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md` and reuse existing diagnostic infrastructure.
*   **Surgical Gating**: Every edit must be followed by `ruff check` (linting) to prevent testing "bad code."
*   **Conductor Delegation**: For complex or high-volume tasks, the Agent should use the Conductor track to delegate work to sub-agents, preserving the primary context window for strategic orchestration.

## BKM-028: High-Fidelity State Machine Debugging
**Objective**: Rapidly validate Hub logic (Lobby -> Ready -> Hibernate) without physical VRAM overhead.

1.  **The STUB Engine**: Utilize `engine="STUB"` to bypass 90s vLLM load times. To boot the system service in STUB mode, use `sudo systemctl edit lab-attendant.service` and add `Environment="LAB_TEST_STUB=1"`.
2.  **Fast Hibernation**: Set `afk_timeout=60` in `acme_lab.py` to observe auto-hibernation cycles in 1 minute.
3.  **Traceability**: Always check `status.json` or the Attendant journal for the `reason` field to verify which trigger caused an ignition.
4.  **Silicon Reset**: Use `sudo systemctl restart lab-attendant.service` to ensure a perfectly clean slate between tests. The `on_shutdown` hook ensures all session orphans are reaped.

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

## BKM-034: OpenAgent Delegation & Playbook Protocol
**Objective**: Establish safe, context-preserving boundary gates for delegating tasks from Gemini (Orchestration) to OpenAgent (Local/Remote Swarm) to minimize token consumption and prevent intent drift.
**Playbook Reference**: [AGY_TO_OPENAGENT_PLAYBOOK.md](../../Portfolio_Dev/AGY_TO_OPENAGENT_PLAYBOOK.md)

1.  **Role Division**:
    *   **Orchestrator (Gemini/Claude)**: Acts as the *Strategic Guardian of the DNA*. Responsible for updating the Master Plan (`SPRINT_PLAN_SPR_XX_X.md`), defining architectural requirements, auditing code changes via git diffs, and running final integration tests.
    *   **Swarm (OpenAgent)**: Executes *Tactical Implementation loops*. Responsible for writing codebase logic, updating test files, and running line-by-line debugging iterations.
2.  **Swarm Agent Category Mapping**:
    *   **Sisyphus-Junior (quick, visual-engineering, writing)**: Spawned automatically via category overrides. Do **NOT** specify `subagent_type: "Sisyphus-Junior"` directly in task tool parameters as it will error.
    *   **Plan-Family Restriction**: Plan-family agents (`plan`, `prometheus`) cannot delegate tasks to other plan-family agents via `task()`.
    *   **Coordinator Restriction**: Coordinator agents (e.g., `prometheus`) own their orchestration loops and are forbidden from being called as subagents. Select worker agents or categories instead.
3.  **Concurrency Deadlock Prevention**: Ollama provider options must set `"maxConcurrency": 5` (or higher) in `opencode.json`. If set to `1` (serialized), the parent orchestrator and child subagent will deadlock when attempting parallel queries to the local model.
4.  **Verification Plan Immutability**: Every task delegated to OpenAgent must have a verbatim, detailed **Verification Plan** detailing the specific tests (e.g., pytest, Playwright) and assertions. OpenAgent is prohibited from marking a task as complete unless the exact verification scripts pass cleanly.
5.  **Token Conservation Guardrails**: For heavy sequence editing, refactoring, or iterative lint-fixing, the prompt must steer OpenAgent to run locally on the RTX 4090 or Groq/DeepSeek Free tiers to preserve Gemini's rate-limited API tokens.
6.  **Forensic Review Gate & Git Ownership**: All git staging, branching, and commits must be handled directly by AGY (cloud orchestrator) as part of the post-implementation review and validation gate, rather than delegating Git operations to local subagent workers. Sisyphus-Junior should focus strictly on local file modifications and test verification. Gemini must review the git diffs, run the system-wide diagnostic runner (`gold_master_batch_runner.sh`), and verify the code against `FeatureTracker.md` before final sprint task checkoff.
7.  **Surgical Handover Prompt Template**: All tasks delegated to OpenAgent must utilize the following structured format. BKM and FEAT context is retrieved from ChromaDB (behavioral_dna / feature_dna collections) rather than injected as raw file content, reducing KV cache pressure on small local models:
    ```markdown
    opencode run -m <provider/model> "
    [GROUNDING CONTEXT — loaded from ChromaDB, not raw file injection]
    - BKM query:  'how to safely patch files atomically'   → retrieves BKM-011, BKM-012
    - FEAT query: 'RAPL telemetry silicon validation'       → retrieves FEAT-098, FEAT-115
    - Active Task: SPRINT_PLAN_SPR_37_0.md#Task-<id>        ← direct pointer (not DNA-managed)

    [TARGET SPECIFICATION]
    - File: <absolute_path_to_target_file>
    - Target Lines/Functions: <target_lines_or_functions>
    - Modification Details: <exact_changes_required>

    [VERIFICATION GATE]
    - Test Command: <validation_script_or_pytest_command>
    - Mandate: You are forbidden from committing unless this test passes.
    "
    ```
    *   **Note**: Raw file links (`file:///...FeatureTracker.md` and `file:///...Protocols.md`) are now handled via the pre-commit-hook-synced ChromaDB collections (`behavioral_dna`, `feature_dna`). Do not re-inject those full files as context; use targeted semantic queries instead. The sprint plan task pointer remains a direct file link as it is ephemeral and not persisted to DNA.
8.  **Session Lifecycle Management (sessions vs. run/play)**:
    *   **`opencode run`**: One-shot, ephemeral execution. Appropriate for single atomic tasks with a clear verification gate (e.g., "fix this specific bug and run this test"). Spawns a new session on each invocation.
    *   **`opencode session`** (preferred for sustained phases): Use named, resumable sessions to persist context across multiple related tasks within a phase or sprint.
    *   **Naming a session**: The session title displayed in `opencode session list` is set at creation time from the first user message. To create a distinctly named session, the first message must be an explicit phase declaration:
        ```bash
        # Start a named session for a specific sprint phase
        opencode run --print-logs "SESSION: Sprint 37 Phase 2 — Persona Polish. Starting task 6.1: IDENTITY_BEDROCK refactor."
        # The session ID is then captured from the output (ses_XXXX)
        ```
    *   **Resuming a session**: Use `opencode --session <session_id>` or `opencode -c` to resume the most recent session:
        ```bash
        opencode --session ses_0c61ebab0ffeRC23pP7kxbiQjU
        opencode -c  # shorthand for continue last session
        ```
    *   **Sprint vs. Phase granularity**: Prefer one session per logical phase (Story or Story group) within a sprint. Avoid single-session-per-sprint as context accumulation over many tasks degrades small model performance. Fork with `--fork` when branching from a stable state:
        ```bash
        opencode --session <ses_id> --fork  # branches context at this point
        ```
    *   **Sustained Sprint Sessions (Persistence)**: When the user requests completing the entire sprint in a single session, Sisyphus should reuse the same subagent session ID (`ses_...` returned by `task()`) for subsequent tasks in the sprint rather than starting a fresh subagent session on each task. Sisyphus must maintain a persistent task checklist/ledger inside the session context.
    *   **Session list audit**: Before starting a new phase, run `opencode session list` and identify the last relevant session ID to resume or fork.
9.  **Playbook Protocol Refinement (Swarm Pain Points)**:
    *   **Strict Verification Gate Enforcement**: Subagents are forbidden from committing code changes if the AST parse (`ast.parse`) or validation tests fail. Committing syntax errors constitutes a severe protocol violation.
    *   **DNA Grounding Enforcement**: Swarm agents must query the `feature_dna` collection (grounded in `FeatureTracker.md`) before making edits to ensure they do not introduce regressional bugs or overwrite active rules.
    *   **Delegation-Guiding Prompts**: Prompts sent to subagents must embed strict boundaries (e.g., `MUST DO` / `MUST NOT DO` rules) to prevent local models from losing context or inventing instructions.
    *   **Named Session Enforcement**: Avoid generating sessions with generic titles (e.g. "Greeting" or "New session"). Always use the `SESSION: Sprint XX Story YY` format on the first query of a session.
    *   **VRAM Inversion Strategy**: Evaluate if the local 4090 VRAM should be inverted: instead of running heavy orchestrators locally (which suffer high latency and context limits), utilize cloud endpoints for orchestration and reservation, and load local models (like `qwen2.5-coder`) primarily for *heavy code generation/refactoring*. Evaluate if coding models still require tool usage or if they can rely on unified diff patches.
10. **DNA Query Translation (Semantic Paraphrasing)**:
    *   **The Principle**: Sisyphus must not query ChromaDB with raw, conversational user prompts verbatim (e.g. `"I want to edit a file"`).
    *   **The Practice**: Sisyphus must translate the user's conversational intent into precise domain-specific search query keywords (e.g. `"safe file write"`, `"atomic file patch"`, `"lint gate"`) before querying the `behavioral_dna` and `feature_dna` collections. This ensures maximum retrieval confidence (minimum distance score).
11. **Explicit Blueprint Prompting (No-Boilerplate Guardrail)**:
    *   **The Principle**: Cloud orchestrators (Gemini) must not delegate open-ended logic or design descriptions to local 14B workers. They must compile exact HTML/CSS blocks, BeautifulSoup scripts, or shell templates directly inside the prompt's `[TARGET SPECIFICATION]`.
    *   **The Practice**: This minimizes local token generations, reduces context overhead, avoids structural hallucinations, and allows the user to review the exact code/design inside the Master Sprint Plan prior to execution.
12. **Mandatory Shell-Based Execution**: All tactical worker delegation must be initiated via the shell-based `opencode` CLI (Method B) rather than using the built-in `invoke_subagent` tool (Method A). The built-in tool is reserved for read-only research tasks or meta-analysis. This ensures all developer tasks are properly registered in the OpenAgent session list and visible in the local TUI/dashboard.
13. **Socket-Activated Server Hibernation & Warm-Up**:
    *   **The Principle**: The OpenAgent server daemon (`opencode-core.service`) is socket-activated by `opencode.socket` on port 4096 and configured with `StopWhenUnneeded=true`. When idle, it shuts down (hibernates) to save memory and GPU resources.
    *   **The Practice**: Before launching a task against the server (via `opencode run --attach http://127.0.0.1:4096/`), Sisyphus must proactively wake the server from hibernation by querying the socket (e.g. running a fast `curl -I http://127.0.0.1:4096/` or `opencode session list | cat`) and waiting 1-2 seconds for initialization to complete before sending the task.

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
