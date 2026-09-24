# Operational Protocols: The Agentic Contract
**Role: Behavioral Guidelines**

> [!IMPORTANT]
> **Purpose:** This document defines the operational guidelines for the Gemini CLI Agent. It is the foundational contract for human-AI collaboration. It specifies how the Agent must behave, communicate, and handle state. It is strictly non-technical.

## BKM-001: The Cold-Start Protocol (Agent Orientation)
**Objective**: Restore the Agent's technical context after a session break or crash.

0.  **Orientation (Bootstrap)**:
    *   Refer to the top-level **[BOOTSTRAP.md](../../BOOTSTRAP_v4.4.md)** for the primary navigational hub and global project context.
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

1.  **Shorthand (QQ)**: Treat "QQ: [Question]" as a literal **Quick Question (Talk Only)**. Evaluates strictly as conversational text analysis. Fulfillment consists **exclusively** of providing a direct, concise answer.
2.  **Absolute Halt**: A "QQ" response constitutes 100% completion of the task. Do not proceed to diagnostics, coding, or log-scraping.
3.  **Persistence of Halt**: Informational or retrospective queries (e.g., "Tell me what you did", "Explain that log") do NOT signal a resumption of work. The Agent MUST remain in the **HALT** state until the user provides an explicit execution directive (e.g., "Fix it", "Proceed", "Apply").

## BKM-005: The Design Studio (Greenlight before Code Change)
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
7.  **Mid-Flight Guidance Capture (Recommended Practice)**: When the operator provides last-minute guidance, constraints, or preference hints within an "AFK" / "Heads Down" prompt, the agent is strongly encouraged to jot down these instructions into the active sprint plan (`SPRINT_PLAN_*.md`) or session notes under a dedicated `## 📝 Operator Directives & Mid-Flight Guidance` section. This acts as a reliable reminder so critical guidance is never forgotten during deep autonomous focus or context compaction.

## BKM-007: Work Completion Report
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Detail**: The report must be comprehensive and clear.
3.  **Content**:
    *   Summary of all completed items with assigned vs completed owner breakdown.
    *   Implications: Impact on VRAM, latency, and security.
    *   **BKM-061 Adversarial Oracle Audit Findings**: Document the findings from the post-sprint oracle sweep, including any glaring architectural, failure-mode, or side-effect deficiencies uncovered and their resolutions.
    *   Rollback Plan: Steps to revert changes if the system becomes unstable.
4.  **Verification**: Re-verify all services (Ollama, vLLM, Intercom) and run the full test suite before handing back control.

## BKM-009: The Checkpoint Protocol (Save State)
**Objective**: Ensure 100% state persistence for session continuity.
**Trigger**: "Checkpoint", "Save", "Close up shop", or end of a feature sprint.

1.  **State Snapshot**: Wrap the current environment state in a <state_snapshot> XML block (Goal, Constraints, Knowledge, Trail, FS State, Recent Actions, Tasks).
2.  **Status Sync**: Update `ProjectStatus.md` and `Portfolio_Dev/00_FEDERATED_STATUS.md`.
3.  **Memory**: Save key architectural decisions to Long-Term Memory.
4.  **Persistence**: `git add .` and `git commit` with a semantic message. (NEVER push).
5.  **Handover**: Provide a 1-sentence summary of "Where we are" and "What to do next."

## BKM-010: Debug Co-Pilot (Interactive Mode)
**Objective**: Maintain diagnostic fidelity during live user/agent collaboration.
**Trigger**: "Interactive Demo", "Co-Pilot Mode", or live debugging requests.

1.  **The Test Plan**: Present a clear plan (What to test, expected outcome) before launching.
2.  **Versioning**: Agent MUST bump the system VERSION (in acme_lab.py) if any client/server logic changed to prevent "Old Code" traps.
3.  **Execute (Blocking)**: Agent runs the co-pilot script and WAITS.
    *   *Timeout*: Tool calls must automatically time out after 300s to prevent Agent lockup.
4.  **Verbal Feedback**: Actively mine logs for user notes (e.g., "Pinky, note that X is broken") received during the session.
5.  **Post-Mortem**: Immediately update `ProjectStatus.md` with findings from both logs and user feedback.

### Canonical Log Black Box Path
All diagnostic forensics MUST reference the canonical black box log:
```
/home/jallred/Dev_Lab/HomeLabAI/src/server.log
```

### FEAT-505: 75-Minute 5x5 Endurance Gauntlet Rule
**Objective**: Ensure engine stability validation across sustained operational intervals.
**Trigger**: Cloud Swarm Run validation, production deployment gates, or long-duration stability certification.

1.  **The 5x5 Mandate**: The engine MUST survive a 75-minute endurance gauntlet with pulse checks at fixed intervals:
    *   **Interval 0 min**: Initial ignition verification
    *   **Interval 5 min**: First stability pulse
    *   **Interval 10 min**: Second stability pulse
    *   **Interval 20 min**: Third stability pulse
    *   **Interval 40 min**: Final stability pulse
    *   **Total Duration**: 75 minutes cumulative

2.  **Pass Criteria**: Engine remains OPERATIONAL at all intervals without crash, stall, or memory leak degradation.

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

## BKM-018: The Orchestrator-First Mandate (Attendant V3 & Live Lab Service Inventory)
**Objective**: Prevent "Zombie States," stale memory footprints, orphan process collisions, and diagnostic blindness caused by manual process manipulation.

1.  **Service Model**: All Lab daemons, proxies, and cognitive engines MUST be managed exclusively as systemd resident services. Direct execution of CLI daemons or background scripts outside of systemd (e.g. `nohup`, `&`, or direct `codex serve` execution) is strictly prohibited.
2.  **Systemd Service Inventory & Topology**:
| Unit Name | Type | Scope | Port / Path | Purpose & Role |
| :--- | :--- | :--- | :--- | :--- |
| **`lab-attendant.service`** | Service | `system` | `:8000` / `:9999` | Acme Lab Attendant & Cognitive Hub Orchestrator (Foyer, ignition, VRAM manager). |
| **`chroma-server.service`** | Service | `user` | `:8001` | Persistent ChromaDB HTTP Vector Database (5 collections). |
| **`headroom-proxy.service`** | Service | `user` | `:8787` | Headroom Token Optimization Proxy for subagents. |
| **`opencode.socket`** | Socket | `user` | `0.0.0.0:4096` | Public Scale-to-Zero LAN Web UI Gateway (`http://192.168.1.238:4096/`). |
| **`opencode-proxy.service`** | Service | `user` | `:4096` ➔ `:4097` | Systemd Socket Proxy (`StopWhenUnneeded=true`, proxies 4096 to 4097). |
| **`opencode-core.service`** | Service | `user` | `127.0.0.1:4097` | Core OpenCode/Codex REST engine (`Headroom wrap codex serve`). |
| **`field-notes.service`** | Service | `system` | `:9001` | Python HTTP Server serving the Field Notes static dashboard. |
| **`acme-pager.service`** | Service | `system` | `:8501` | Neural Pager Streamlit activity log dashboard. |
| **`field-notes-nibbler.service`** | Service | `user` | Background | Continuous load-aware note scanner and indexer. |
| **`field-notes-nightly.timer`** | Timer | `user` | `02:00 AM` | Nightly 2:00 AM note synthesis & date aggregation sweep. |

3.  **Proxy Usage**: All agentic orchestration must flow through the **Native MCP Tools** (`lab_start`, `lab_stop`, `lab_quiesce`). These tools act as a stateless proxy to the resident service.
| Tool | Intent | Physical Action |
| :--- | :--- | :--- |
| **`lab_start`** | Primary Ignition | **Atomic Scrub**: Executes a PGID-aware purge of all previous Lab processes before launching the Hub and Engine. **No manual cleanup required.** |
| **`lab_stop`** | Full Shutdown | **Assassin Activation**: Immediately terminates all process groups holding Lab ports (8088, 8765) and settles the silicon. |
| **`lab_quiesce`** | Maintenance Lock | **Persistence Gate**: Sets a `maintenance.lock`, kills all residents, and enters a passive state where the Watchdog is disabled. Use this for driver updates or manual config testing. |
| **`lab_heartbeat`** | Vitals Audit | **Forensic Truth**: Returns the physical port status, VRAM used/total, and the unique `[BOOT_HASH]` to verify which code version is actually resident. |
| **`lab_ignition`** | Lock Clearance | **Emergency Override**: Clears any existing `maintenance.lock` files but does NOT start models. Follow this with `lab_start`. |

4.  **Critical REST**: The REST API (port 9999 / 8000) is a critical infrastructure layer that enables `status.html` remote control and backend communication for the MCP Proxy.
5.  **Restriction**: Do not use manual `pkill`, `kill`, `nohup`, or direct CLI execution of `python3 src/acme_lab.py` or `codex serve`.
6.  **Code Reload & Restart Mandate (CRITICAL)**: Any codebase modifications made to Foyer routing (`router.py`, `cognitive_hub.py`), node adapters (`loader.py`, `archive_node.py`), or Attendant services MUST be followed immediately by `sudo systemctl restart lab-attendant.service`. Running integration tests or live queries against a running lab without restarting the service tests stale memory footprints, leading to false validation passes.
7.  **Live Integration Testing Mandate**: All integration test suites (`test_integration_*.py`, `live_fire_integration.py`) MUST actively target and validate against the live running lab services (`lab-attendant.service` on `:8000`, `chroma-server.service` on `:8001`, and Node KENDER on `:11434`).
8.  **Non-Blocking HyDE Synthesis**: Triage and HyDE vector generation must NEVER block on local VRAM status or output empty filler. When the local engine is warming (`not get_vram_status()`), `cognitive_hub.py` must route `triage_mode_context` immediately to Deep Thought on KENDER (`192.168.1.26:11434`) for instant 3-part Composite HyDE query synthesis (`[VALIDATION] | [STRATEGY] | [SRE]`).

## BKM-024: Validation-Aware Synchronization & Live Verification
**Objective**: Lab must be current and left in a recoverable state that will recover to live automatically, ensuring physical daemon processes and silicon endpoints match active sprint code before task certification.

1.  **The Recoverable State Invariant**:
    *   **Liveness $\neq$ Static Immobility**: Heavy compute operations (Nightly Forge training, VRAM reallocation, deep service resets) are legitimate lifecycle transitions. Quiescing or restarting the lab is expected when needed.
    *   **Automatic Self-Healing**: Any process that claims exclusive hardware/VRAM or pauses the lab must be protected by a mutex/lockfile (`run/maintenance.lock`) and include a deterministic error-recovery path (`finally:` block) that wakes or restarts the service back to `OPERATIONAL` without requiring human intervention.
2.  **Two-Tier Verification Standard**:
    *   **Tier 1 (Fast Mock Isolation)**: Unit tests and mocked suites are encouraged for rapid iteration during local coding, offline AST/schema parsing, and edge-case unit verification.
    *   **Tier 2 (Mandatory Live Certification)**: No task or bugfix may be marked complete based on mock tests alone. The Agent must verify against the active running daemon (`http://127.0.0.1:8765/status` matching local Git HEAD) and reachable hardware silicon seats.
3.  **Sync-Gate & Fresh Bytecode (Git Anchor Contract)**: Pytest automatically checks local Git HEAD against the served boot commit (`git_anchor.json` == `daemon.boot_commit` == `git rev-parse HEAD`). If a mismatch is detected, the Agent must trigger a daemon restart/reload rather than ignoring the stale state.
4.  **State Trust**: Do not assume background processes persisted cleanly across git commits or code refactors. Re-verify liveness and run live integration queries after every service restart.

## BKM-020: High-Fidelity Sprint Documentation (Intent Preservation)
**Objective**: Prevent 'Loss of Intent' during context-window shifts or session restores.
1.  **Task Verbosity**: Tasks must NOT be one-liners. They must include the 'Why' (Rationale), the 'How' (Mechanism), and the 'Proof' (Verification). Include verbatim snippets/reports from discussions to anchor the task.
2.  **Historical Trace**: Sprints must document the forensic anchors (logs, code fragments) that justify the change.
3.  **Absolute Append**: Do NOT re-write, overwrite, or summarize existing phases of an active sprint plan to 'save space.' New requirements or findings MUST be appended as new phases at the end of the document.
4.  **No Summarization**: Do not slim down technical requirements for brevity. Detail is the only protection against agentic regression. Detail-rich reporting is the standard for intent preservation.
5.  **The Pre-Lock Forensic Gap Audit (Doc vs. Discussion Review)**:
    Before requesting user Greenlight or finalizing any Sprint Plan, the orchestrator MUST perform a forensic comparison between the conversational design session and the draft markdown document across 5 mandatory verification gates:
    * 🔍 **Localized Root Causes**: Does every individual story contain a "Why It Broke & Root Cause" callout box? (Subagents dispatched via `delegate.py` see only their story in isolation; root cause context prevents blind patching).
    * 📌 **Buried Code Pointers**: Are exact filenames and line numbers cited for existing/reusable utilities (e.g., test probes, socket checkers, helper classes) to prevent reinventing the wheel?
    * 🧪 **Literal Test Batteries**: Are concrete test input strings, phrases, and assertions printed verbatim in the story specification (never summarized as "test edge cases")?
    * 🏛️ **Persona & Prompt Pillars**: Are shared bedrock environment prompts, interest levels, and turn-stage tags explicitly anchored in the prompt requirements?
    * 📡 **Telemetry & Routing Contracts**: Are exact WebSocket packet types, channel names, and UI console targets defined?

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
*   **Structure**: Every task/story MUST include:
    - **How**: Technical implementation path.
    - **Why**: Strategic architectural rationale.
    - **Assigned Owner**: Explicit execution tier (`[SWARM:LOCAL]`, `[SWARM:CLOUD]`, or `[AGY:PRIMARY]`). Direct code modifications by AGY on swarm-tagged stories are strictly forbidden per `BKM-049`.
    - **Target Files**: Explicit file paths targeted for modification.
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
4.  **Server Reset**: Use `sudo systemctl restart lab-attendant.service` to ensure a perfectly clean slate between tests. The `on_shutdown` hook ensures all session orphans are reaped.
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

## BKM-034: Swarm Delegation — Dual Orchestrator Protocol
**Playbook Reference:** [Portfolio_Dev/docs/playbooks/OPENAGENT_HANDOVER_PLAYBOOK.md](../../Portfolio_Dev/docs/playbooks/OPENAGENT_HANDOVER_PLAYBOOK.md)  
**Feature Anchor:** `[BKM-034]` / `[FEAT-552]` / `[FEAT-515]`  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
All tactical engineering tasks delegated to the autonomous swarm communicate exclusively through the standardized launcher [`HomeLabAI/src/tests/delegate.py`](https://github.com/kEnder242/HomeLabAI/blob/main/src/tests/delegate.py) on REST port `4097` (`codex serve`).

### 2. Live CLI Introspection
To inspect live flags, choices, and defaults without reading source code:
```bash
HomeLabAI/.venv/bin/python3 HomeLabAI/src/tests/delegate.py --help
```

### 3. Canonical Invocation Template
```bash
HomeLabAI/.venv/bin/python3 HomeLabAI/src/tests/delegate.py \
  --sprint <N> \
  --story <X.Y> \
  --title "<Story Title>" \
  --reference <Sprint_Plan_Path> \
  --target "<comma_separated_target_files>" \
  --mode {execute|plan|investigate|oracle} \
  {--local-only | --cloud-only} \
  --details "<4_Anchor_Specification>"
```

### 4. Invariant Rules
1. **Sovereign Execution Tiers:**
   * `--local-only` (Default): Routes to local silicon (Atlas on Kender RTX 4070 $\rightarrow$ Junior on M5 Air).
   * `--cloud-only`: Routes directly to Prometheus / Cloud Swarm.
2. **Single-Tenant Zombie Eviction:** `delegate.py` automatically sweeps and aborts orphaned sessions on port `4097` upon pre-flight and termination.
3. **Payload Structure ([BKM-043]):** All `--details` specifications must adhere strictly to the 4-Anchor Standard (`Import Anchor`, `Path Anchor`, `Exact Signatures`, `Output Shape Template`).
4. **Diagnostic Escalation ([BKM-049]):** Interactive halts or blockers emit Exit Code 2 (`AWAITING_INPUT`) for orchestrator intervention via `--resume <session_id> --answer <choice>`.

---

## BKM-035: Lab/Feature Taxonomy Separation Protocol
**Objective**: Maintain a clear boundary between the Lab Infrastructure (management systems) and Resident Features (domain business logic) to prevent naming collisions and design confusion.

1.  **Scope Division**:
    *   **`[LAB_INFRA]` (Infrastructure)**: Pertains to Foyer, Attendant, WebSockets, IPC/Intercom, agent cognitive engines (Dreaming, Coherence Critic), and daemon management. Documented under `HomeLabAI/docs/LAB_INFRASTRUCTURE.md`.
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

## BKM-040: Virtual Environment Hygiene & Git Curation
**Objective**: Prevent virtual environment context-bleeding and indexing bloat across subagent swarms.

1. **Single Canonical Venv**: The primary canonical Python environment is pre-configured at `HomeLabAI/.venv`. Always activate or use `HomeLabAI/.venv/bin/python` for all execution. Workspace sub-directories (e.g., `Portfolio_Dev`) must NOT contain local `venv` or `.venv` copies.
2. **Git Ignore Hardening**: Every workspace repository must explicitly ignore `venv/`, `.venv/`, `env/`, and `*.egg-info/` in its root `.gitignore`.
3. **Agent Indexing Isolation**: Agentic search/scan tools (e.g., `opencode`, `codex`, `ripgrep`) must respect `.gitignore` to avoid indexing thousands of site-packages files that cause memory ballooning.
4. **Pre-Commit Verification**: Before staging changes, agents must verify `git status --porcelain` contains no untracked environment or binary build artifacts.

---

## BKM-039: RAG Taxonomy Separation & HyDE LoRA Tabling Protocol
**Objective:** Maintain strict separation between Agent Behavioral DNA and User Work History while standardizing prompt synthesis over fine-tuning.

1. **Taxonomy Boundary**:
   - **Agent DNA (`behavioral_dna`, `feature_dna`)**: System operational instructions, BKM protocols, feature mechanisms.
   - **User Work History (`career_ledger`, `artifact_vault`, `lab_journal`)**: 18-year technical career history, resume ground truth, hardware validation logs, field notes.
2. **LoRA Fine-Tuning Tabling Decision**:
   - HyDE synthesis relies on structured prompt templates (Unified Intent-HyDE) rather than custom LoRA weights.
   - Prompt-based multi-voice synthesis maintains 100% adaptability without model quantization drift or LoRA reloading overhead.

---

## BKM-041: Automagic DNA Injection & CLaRa MCP Bridge (The Agent Context Architecture)
**Objective**: Guarantee that builder agents (AGY, OpenAgent) automagically receive grounded FEAT specs, BKM protocols, and architectural laws in their prompt context before every turn — while providing on-demand tool access for deep exact-ID lookups — at zero VRAM/GPU cost.

1. **The Architecture (Dual-Channel Context Grounding)**:
   Agent context grounding relies on two complementary channels working together:

   ```
   [Upstream Sources]
   FeatureTracker.md (FEATs) + Protocols.md (BKMs) + LAB_INFRASTRUCTURE.md
          │
          ▼ (git pre-commit hook: sync_chroma_dna.py)
   [ChromaDB Vector Server] (port 8001, chroma-server.service)
          │
          ├───► CHANNEL 1: AUTOMAGIC INJECTION (ICM + BeforeAgent Hook)
          │     `~/.config/icm/config.toml` (provider="chroma", chroma_url="http://localhost:8001")
          │     `settings.json` ("BeforeAgent": icm hook prompt)
          │     ==> Automagically injects top vector matches into system prompt BEFORE turn 1.
          │
          └───► CHANNEL 2: ON-DEMAND MCP BRIDGE (clara-dna MCP Server)
                `AcmeLab/src/clara_dna_mcp_server.py` (chromadb.HttpClient -> :8001)
                `~/.gemini/config/mcp_config.json` (AGY) / `.opencode.json` (OpenAgent)
                ==> Exposes query_dna(), get_protocol(), list_collections() for exact lookups.
   ```

2. **Channel 1: Automagic Context Injection (ICM Hook)**:
   * **Turnkey Engine**: ICM (`/home/jallred/.local/bin/icm`) acts as the native prompt-injection plugin.
   * **Configuration**: `~/.config/icm/config.toml` sets `provider = "chroma"` and `chroma_url = "http://localhost:8001"`. 
   * **Port Law**: **Port 8001 is ChromaDB.** (Port 8000 is Prometheus RAPL Exporter — pointing ICM to 8000 breaks vector retrieval).
   * **Hook Registration**: `settings.json` registers `icm hook prompt` under `BeforeAgent`. On every prompt, ICM queries ChromaDB `:8001` via vector similarity and automagically prepends relevant context to the prompt before the LLM generates a response.

3. **Channel 2: On-Demand Tool Bridge (`clara-dna` MCP Server)**:
   * **Purpose**: Allows agents to run surgical, targeted lookups during execution (e.g. `get_protocol("BKM-015")` or `query_dna("feature_dna", "Unity Pattern")`).
   * **Zero Overhead**: Uses `chromadb.HttpClient` to talk to port 8001 over HTTP. Zero VRAM, zero GPU, <1MB RAM.
   * **Registration**:
     * **AGY (Antigravity CLI v1.1.10)**: Registered in `~/.gemini/config/mcp_config.json` under `mcpServers.clara-dna`.
     * **OpenAgent (OpenCode)**: Registered in `HomeLabAI/.opencode.json` under `mcp.clara-dna`.

4. **Relationship & Identity Boundaries**:
   * **AGY Identity**: AGY is Antigravity CLI (binary: `~/.local/bin/agy`). Config files live at `~/.gemini/antigravity-cli/settings.json` for settings/hooks and `~/.gemini/config/mcp_config.json` for MCP servers.
   * **ICM vs. CLaRa DNA**: ICM remembers *what happened* across sessions; CLaRa DNA knows *what the architectural rules are* from ChromaDB `:8001`.
   * **Lab HyDE vs. Agent Injection**: Cognitive Hub HyDE ([FEAT-436]) handles *user-facing* RAG for the lab runtime; ICM + CLaRa DNA handles *agent-facing* grounding for code builders.

---

## BKM-042: Zero-Thrash Delegation Protocol
**Date:** August 7, 2026  
**Objective:** Mandate 4 strict prompt construction rules when dispatching tasks via `delegate.py` to eliminate OpenAgent subagent search loops, path retries, and context thrash.

1. **Path Pre-Verification**: Always run `find` or `view_file` to confirm exact file paths before passing `--reference`, `--target`, and details to `delegate.py`. Never guess directory structures.
2. **Atomic Story Scoping**: Keep stories strictly atomic to 1 feature / 1 core target component per story. Never bundle host OS hardening with application code features in a single prompt.
3. **Explicit SystemD & OS Scope**: Explicitly state in the task details whether a service is system-level (`/etc/systemd/system/` requiring `sudo`) or userland (`systemctl --user`).
4. **Function Anchor Targeting**: Include exact function names (e.g. `startMic()`) and line range anchors in the prompt details so sub-agents skip whole-file scan passes.

---

## BKM-035: The Fourth Wall Feedback Protocol (Semantic Critique & Validation Ledger Auto-Population)
**Objective**: Transform user natural language disagreements and conversational corrections into instant, permanent evaluation failure tests and rubric constraints without brittle UI vote buttons or rigid keyword matches.

1. **The Language-First Mandate**:
   * The user is the ultimate domain expert and oracle. When the user speaks to the "fourth wall" or expresses disagreement (e.g., *"Wait, that's wrong, RAPL MSR 0x610 is PKG limit, not DRAM"* or *"Pinky, note that your triage missed the AER register"*), the system must intercept this semantically rather than treating it as a new ungrounded topic.
   * **BKM-015 Anti-Hardcoding Rule**: Intent detection for user critiques MUST use semantic vector classification (`GROUNDING_CORRECTION` intent), never rigid keyword string matching.

2. **In-Session Behavioral Flow (Interactive Refinement Prompt)**:
   * **Acknowledgment**: Pinky acknowledges the correction in-character with high brevity (e.g. *"Narf! Got it, MSR 0x610 is the PKG energy limit."*).
   * **Refinement Inquiry**: Pinky asks one targeted follow-up question to clarify boundary conditions, register masks, or reproduction steps (e.g. *"Should I clamp the default power limit window to 28 seconds for Haswell?"*).
   * **No Defensiveness**: The agent must never argue, hallucinate justifications, or provide conversational filler when corrected.

3. **Downstream Ledger & Distillation Automation**:
   * **Automated Failure Record**: Write an instant `FAIL` entry to `Portfolio_Dev/field_notes/data/validation_ledger.jsonl`:
     ```json
     {
       "timestamp": "ISO-8601",
       "query": "<original_user_query>",
       "verdict": "FAIL",
       "flawed_output": "<previous_assistant_response>",
       "ground_truth": "<user_correction_text>",
       "source": "CO_PILOT_FOURTH_WALL"
     }
     ```
    * **Rubric Tuning (Netflix Pattern)**: Automatically append the user's assertion as a ground-truth boolean constraint to the Universal Epistemic Evaluator.

---

## BKM-043: Master 4-Anchor Prompt Standard (Surgical Code Anchoring & Story Template)
**Date:** August 25, 2026 (Updated September 2, 2026)  
**Objective**: Eliminate subagent design-by-inference, whole-file re-scan thrash, and import/path errors by baking 4 mandatory, grep-resilient anchors and explicit tool contracts directly into every sprint story specification.

### 1. The 4 Concrete Anchors (Baked Directly Into Story Text)
1. **Anchor 1: Grep-Stable Code Anchor**:
   * Must specify exact target file, target function/class, and approximate line number with a grep fallback string.
   * *Formula*: `"In <file>, edit inside def <func>() starting around line <N> (grep: '<unique_signature>' if lines shifted)"`.
   * *Purpose*: Prevents subagents from whole-file re-reading or getting lost when prior edits shift line numbers.

2. **Anchor 2: Import & Root Namespace Anchor**:
   * Must specify explicit root namespace convention.
   * *Formula*: `"PYTHONPATH=src: use 'from logic.x import y'` (never relative `..` or `src.logic.x`)"`.
   * *Purpose*: Eliminates Python module resolution mismatches across workspaces.

3. **Anchor 3: Path Resilience Anchor**:
   * Must mandate stdlib `pathlib.Path(__file__).resolve().parent...` fallbacks for all configuration and asset file reads.
   * *Purpose*: Eliminates `FileNotFoundError` when commands run from different working directories.

4. **Anchor 4: Surgical Delta & Concrete Output Template**:
   * Must provide concrete dataclass, dictionary schema, and return type examples rather than abstract prose instructions.
   * *Purpose*: Completely eliminates "design-by-inference" where subagents invent incompatible dictionary keys.

### 2. Mandatory Sprint Story Markdown Template
Every story in a sprint plan MUST be authored using this exact self-contained template so Layer 3 workers have all tool and code requirements baked directly at their fingertips:

```markdown
### 📊 Story XX.Y: <Title> (`[FEAT-XXX]`)
* **Status:** `[PENDING DELEGATION]`
* **Assigned Execution Mode:** `[SWARM DELEGATION: ATLAS + JUNIOR]` (via `delegate.py` on REST port 4097)
* **Objective:** <1-2 sentence concise goal>
* **Target Files:**
  * `<path/to/target_file>`
  * `<path/to/test_file>`
* **4-Anchor Specification (BKM-043):**
  * **Anchor 1 (Symbol Anchor):** In `<target_file>`, edit inside `<class/func>` (around line N, grep: '<signature>').
  * **Anchor 2 (Data Flow / Root Imports):** `PYTHONPATH=src: use 'from logic.x import y'`.
  * **Anchor 3 (Schema / Code Stub):** Exact dataclass, dictionary keys, or literal code diff.
  * **Anchor 4 (Path Resilience):** Mandate `Path(__file__).resolve().parent` fallbacks.
* **Tool Invocation Law:**
  * Modifying Existing Files: Use `clara-dna_safe_patch` with exact `old_pattern` and `new_pattern`.
  * Creating New Files: Use standard `write` tool.
  * Anti-Exploratory: Research is done. Never run repo-wide search or grep.
* **Acceptance Criteria:**
  1. <criterion 1>
  2. <criterion 2>
* **Verification Command:** `pytest <path/to/test_file> -v`
```

---

## BKM-044: Lab Attendant Ignition & Quiescence Law (Zero Direct Hardware Bypassing)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                         BKM-044: LAB ATTENDANT IGNITION STANDARD                         │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ❌ FORBIDDEN: Direct manual shell execution of start_vllm.sh, python router.py,        │
│                or backgrounding unmanaged engine daemons.                                │
│                                                                                          │
│  ✅ MANDATORY: All engine state transitions (Wake/Sleep/Ignite) MUST be dispatched       │
│                exclusively through the Lab Attendant REST API (Port 8765):               │
│                                                                                          │
│    1. Wake / Ignite:     curl -X POST http://127.0.0.1:8765/wake                         │
│    2. Sleep / Free VRAM: curl -X POST http://127.0.0.1:8765/sleep                        │
│    3. State Poll:        curl -s http://127.0.0.1:8765/status | jq .state                │
│                                                                                          │
│  SILICON RULES:                                                                          │
│  - Respect the 60s Quiescence Window [FEAT-136] between state transitions.               │
│  - VRAM Utilization floor is capped at 0.55 (8k context) to protect the physical Xorg   │
│    display server running on the primary RTX 2080 Ti adapter.                            │
│  - SELF-SYNCHRONIZING RESTART: Lab restart/wake operations handle completion internally  │
│    and return when finished. Agents must NEVER poll in a loop or schedule poll timers.   │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## BKM-045: Removable USB FOB Kernel BDI Isolation & Unmounted-at-Rest Protocol

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                   BKM-045: REMOVABLE USB FOB HARDENING STANDARD                          │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ❌ FORBIDDEN: Auto-mounting offline hardware recovery USBs (e.g. ASUS BIOS Flashback)    │
│                in Linux runtime userspace (/etc/fstab with 'auto' or desktop udisks2).   │
│                                                                                          │
│  ✅ MANDATORY FOUR-LAYER DEFENSE:                                                        │
│                                                                                          │
│    1. Unmounted-at-Rest (/etc/fstab):                                                    │
│       LABEL=Z87P_FLBK /media/jallred/Z87P_FLBK1 vfat noauto,user,rw,noatime,umask=000   │
│       (Drive physically remains plugged in rear BIOS Flashback port, unmounted in OS).   │
│                                                                                          │
│    2. Desktop Auto-Mount Suppression (/etc/udev/rules.d/99-bios-flashback-ignore.rules): │
│       ENV{ID_FS_LABEL}=="Z87P_FLBK", ENV{UDISKS_IGNORE}="1"                             │
│       ENV{ID_FS_UUID}=="2FDD-8136", ENV{UDISKS_IGNORE}="1"                              │
│                                                                                          │
│    3. Kernel BDI Writeback Throttling (/etc/udev/rules.d/90-usb-bdi-throttle.rules):     │
│       SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_BUS}=="usb",                      │
│       ATTR{bdi/strict_limit}="1", ATTR{bdi/max_ratio}="1"                                │
│       (Caps USB dirty RAM cache to 1%, preventing global sync() stalls in D-State).      │
│                                                                                          │
│    4. Locate Search Exclusion (/etc/updatedb.conf):                                      │
│       PRUNEPATHS contains /media/jallred/Z87P_FLBK1 to prevent background indexer locks. │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## BKM-047: Local Silicon Memory Ceilings & Bicameral Swarm Topology

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                   BKM-047: LOCAL SILICON MEMORY CEILINGS & BICAMERAL SWARM TOPOLOGY      │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  THE HARDWARE ASYMMETRY REALITY:                                                         │
│  Federated bicameral swarms pair distinct silicon architectures with competing memory    │
│  profiles. Inverting their operational roles causes instant thrashing or OOM crashes.    │
│                                                                                          │
│  1. Node Kender (Windows RTX 4090 24GB VRAM / Ollama):                                  │
│     - Model: hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL (9.16 GB resident).                │
│     - Headroom: ~14.8 GB dedicated VRAM for KV cache + dynamic host RAM paging.          │
│     - Swarm Roles:                                                                       │
│       * Layer 2 Conductor (Atlas): Absorbs sprint plan, sequences cascade dependencies.  │
│       * Stage 2 Scout (Librarian): Read/grep anchor discovery (NO file edits, NO bash).  │
│       * Stage 4 Verifier (Momus): Bash/pytest runner & traceback parser (NO code edits). │
│                                                                                          │
│  2. Node Brain (Apple M5 Air 32GB Unified Memory / oMLX via Headroom :8002):              │
│     - Model: mlx-community--Qwen3.8-27B-4bit (15.2 GB resident).                         │
│     - Headroom Proxy (:8002): Compresses prompt prefill KV caches to prevent Metal OOM.  │
│     - Metal Memory Ceiling: iogpu.wired_limit_mb caps wired GPU memory at ~24.46 GB.     │
│     - Swarm Roles:                                                                       │
│       * Stage 3 Surgical Worker (Sisyphus-Junior): Bounded (<1.5k tok) code patching.    │
│       * Blocker Surgeon (Daedalus): 27B deep-reasoning AST/syntax solver summoned ONLY   │
│         when Junior or verification fails. Bounded context (<1.5k tok), no bash.         │
│                                                                                          │
│  THE 4-STAGE AGENT CASCADE (AUTONOMOUS SWARM FLOW):                                      │
│  To prevent Layer 1 (AGY) from excessive "spoon-feeding" token traps while protecting    │
│  small local model contexts, Atlas drives a 4-stage sequential subagent cascade:         │
│  1. Stage 1 (Atlas): Ingest sprint plan on disk, establish task sequence.                │
│  2. Stage 2 (Librarian): Inspect target code & extract exact incumbent anchors/imports.  │
│  3. Stage 3 (Sisyphus-Junior): Apply surgical diff via clara-dna_safe_patch.            │
│  4. Stage 4 (Momus): Execute verification command via bash, parse and digest tracebacks. │
│  * Escalation Gate: If Momus fails, Atlas summons Daedalus on M5 Air 27B to resolve it. │
│  * Ephemeral Context Rule: Each stage runs via task(), auto-flushing context on exit.    │
│                                                                                          │
│  SCARS RETROSPECTIVE:                                                                    │
│  - Scar #1: Feeding broad sprint context directly to M5 Air 27B caused silent kernel     │
│    hangs when Metal prefill activation buffers exceeded wired unified memory limits.     │
│  - Scar #2: Atlas attempting direct file editing caused hallucinated imports; resolved   │
│    by hard-pinning Atlas permissions to edit:deny and delegating via task().             │
│  - Scar #3: Junior running tests polluted its context with verbose traceback dumps;     │
│    resolved by isolating test execution and linting to Momus (Stage 4).                  │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## BKM-048: Just-in-Time (JIT) Context Interleaving & The "Fingertips" Protocol
**Feature Anchor:** `[FEAT-515]` / `[BKM-048]`  
**Domain:** Layered Swarm Delegation, Token Budget Optimization, and On-Disk JIT Execution  
**Status:** ACTIVE / MANDATORY  

### 1. The Core Law: Bake Context In (Do Not Require Search Lookups)
* **❌ FORBIDDEN:** Telling a local 14B/27B worker to "Go query ChromaDB", "Go look up BKM-043", or "Explore the codebase for imports". Local attention spans dilute instantly across multi-step research turns, causing memory ceilings and hallucinations.
* **✅ THE "FINGERTIPS" LAW:** All necessary context, symbol anchors, import paths, code stubs, and tool schemas MUST be **baked directly into the sprint story on disk**.
* **POINTER-BASED DELEGATION:** 
  1. **Layer 1 (AGY)** writes the complete self-contained 4-anchor story block into the sprint document.
  2. **Layer 2 (Atlas)** routes a lean pointer (`< 300` tokens) via `task(category="...", prompt="Execute Story X in <sprint_doc> (Section: Story X)...")`.
  3. **Layer 3 (Junior)** reads its specific story section on disk. Everything it needs is directly at its fingertips in that section—zero search, zero tool exploration required.

### 2. Three-Layer JIT Authoring & Execution Architecture
* **Layer 1: Strategic Guardian (AGY / Gemini)** → Guides: `[BKM-030]` & `[BKM-043]`
  * Authors the Sprint Plan as the canonical on-disk "JIT Container" using clean Markdown (no ASCII art boxes).
  * Bakes the 4 anchors, tool laws, and pytest commands directly into every story section.
* **Layer 2: Tactical Router (Atlas on Windows RTX 4090 / Ollama)** → Guide: `[BKM-034]`
  * Absorbs broad sprint context (14.8 GB KV cache headroom).
  * Strict L2 Invariants: Pure router. NEVER writes code or edits files.
  * Emits exactly ONE pointer dispatch per turn. Never serializes large code blocks across `task()` parameters.
  * Relays Junior's blockers straight up to AGY; provides a 2-sentence handover reflection on instruction clarity.
* **Layer 3: Fast Surgical Worker (Sisyphus-Junior on KENDER 4090 / M5 Air)** → Guide: `[BKM-048]`
  * Reads its exact 4-anchor section on disk (< 1,500 tokens).
  * Strict L3 Invariants: Anti-exploratory. Heavy tools (`icm_*`, `websearch_*`, `codegraph_*`) denied via `[BKM-051]`.
  * Executes edits via `clara-dna_safe_patch` (or `write` for new files) and runs assigned `pytest`.
  * Halts immediately on missing types; emits `[BLOCKER REPORT: <CATEGORY>] <details>` upward.

### 3. Harness Resilience & Escalation Protocol
* If a subagent terminates on an interactive popup or silent finish (`finish=unknown`), `delegate.py` breaks out with code 2 (`AWAITING_INPUT`) and provides a resume command.
* *"When delegation stumbles, we halt the sprint to fix the harness; we never manually bypass the failure to finish the sprint."*

---

## BKM-051: Subagent MCP Tool Scoping & Context Ballast Protocol
**Feature Anchor:** `[FEAT-526]` / `[BKM-051]`  
**Domain:** OpenAgent Swarm Topology, MCP Overhead Mitigation & Subagent Prompt Budget  
**Status:** ACTIVE / MANDATORY  

#### 1. The Tool Schema Overhead Problem
When an MCP server exposes many tools (e.g. ICM with 31 tools, LSP with 15 tools), OpenCode injects the full JSON Schema for every single tool into the system prompt of every agent. For child workers, this creates **24,488 tokens of static tool ballast** before reading any code, causing:
1. Massive prefill dead-air (90+ seconds on unified memory hosts).
2. Metal VRAM exhaustion (`AI_APICallError: oMLX prefill memory guard rejected this prompt`).
3. Diluted model attention across dozens of irrelevant tools.

#### 2. The Tool Scoping Law
1. **Architect Nodes (Atlas / Sisyphus):** Granted full access to `icm_*`, `clara-dna_*`, and research tools to formulate structured plans and recall historical context.
2. **Worker Nodes (Sisyphus-Junior / Hephaestus):** MUST have heavy and unused MCP tools denied in `oh-my-openagent.json`:
   ```json
   "permission": {
     "edit": "allow",
     "icm_*": "deny",
     "websearch_*": "deny",
     "codegraph_*": "deny",
     "question": "deny"
   }
   ```
3. **Target Worker Input Ceiling:** A worker subagent's initial prompt MUST stay below **1,500 tokens**.

---

## BKM-049: Tri-Loop Story Delegation & Diagnostic Protocol
**Feature Anchor:** `[FEAT-522]` / `[BKM-049]`  
**Domain:** Swarm Delegation, Autonomous Subagent Execution & Harness Diagnostics  
**Status:** ACTIVE / MANDATORY  

#### 1. The Tri-Loop Law
1. **Execution Tiers & Retry Boundaries:**
   * **`[SWARM:LOCAL]` (The 3-Loop Diagnostic Mandate):** When targeting sovereign local silicon (Windows RTX 4090 Atlas + macOS M5 Air Junior), the orchestrator MUST execute up to **3 full diagnostic remediation rounds on local silicon** (Attempt 1a → diagnose & fix harness/prompt/knobs → Attempt 1b → Attempt 1c). Any failure on Attempt 1 requires the orchestrator to diagnose the failure, adjust the harness/config/prompt, and retry on local. Local silicon is NEVER abandoned after a single failure. Only after all 3 diagnosed local attempts are exhausted does the story escalate to Cloud Swarm (`[SWARM:CLOUD]`), followed by Primary Takeover (`[AGY:TAKEOVER]`).
   * **`[SWARM:CLOUD]` (Direct Cloud Route):** When a story is tagged `[SWARM:CLOUD]`, local attempts are skipped entirely. The dispatch routes directly to Cloud Swarm (Groq / OpenCode Cloud / Big-Pickle / Cohere). If Cloud Swarm fails, it skips local retries and routes straight to Primary Takeover (`[AGY:TAKEOVER]`).
   * **`[AGY:PRIMARY]` (Direct Architectural Core):** Architectural scaffolding, protocol governance, and schema bootstrap executed directly by the primary agent.
2. **Never Blindly Retry:** A retry within local silicon (or between escalation tiers) is strictly defined as an execution attempt preceded by root-cause diagnosis. Simply tweaking prompt wording without fixing underlying tool/permission/harness mismatch is an invariant violation.
3. **Safe-Patch Mandate (Anti-Bash-Clobber):** Subagents MUST NOT use destructive bash file writes (`cat << 'EOF' >` or `echo >`) on existing codebase files. Subagents must invoke `clara-dna_safe_patch` (or atomic patchers) for existing files, reserving `write` strictly for new standalone files.

#### 2. Mandatory Diagnostics Between Retries
Before initiating a retry for a stalled, failed, or timed-out subagent, the orchestrator MUST perform three diagnostic probes:
1. **Server & Silicon State:**
   - Probe inference endpoints (`curl http://192.168.1.46:8000/v1/models`, `nvidia-smi`).
   - Check socket states (`ss -tulpn | grep 4097` or target port) to ensure child connections are not hanging.
2. **Session Transcripts & Logs:**
   - Inspect OpenCode / subagent transcripts for syntax loops, compaction triggers, or unhandled tool rejections.
   - Verify whether OpenCode auto-compaction hijacked the context window.
3. **Harness & Configuration Audit:**
   - Audit `delegate.py` and `opencode.json` for prompt contradictions (e.g. Single Task Law vs. micro-patterns).
   - Verify file permissions, diff patch formats, and linting constraints.

#### 3. Root Cause Escalation Matrix
| Failure Symptom | Diagnostic Finding | Remediation Required Before Retry |
| :--- | :--- | :--- |
| `"Model is busy"` / 503 | Parallel requests exceeded single-stream ceiling | Enforce Single Task Law; serialize dispatches. |
| Subagent freezes mid-read | Auto-compaction agent spawned | Set `"compaction": {"auto": false}` in `opencode.json`. |
| Ruff / Syntax loop | Indentation or multiline whitespace slip | Provide explicit AST line anchors or simplify patch scope. |
| Bash clobber attempt | Subagent attempted `echo >` on existing file | Inject explicit `clara-dna_safe_patch` JSON tool call schema into prompt. |
| Code 3: Silent Failure | 0 text tokens streamed; session deadlocked | Check inference server health; escalate to Attempt 2 (Cloud Swarm). |

#### 4. The 5-Minute Watchdog & Inspection Gate Law
1. **Inspection Gate, Not an Automatic Kill:** The 5-minute watchdog ceiling is an **Inspection Gate**, not a blind termination trigger. Reaching 5 minutes does NOT mean immediate cancellation.
2. **Active Progress Probe:** At the 5-minute mark, the orchestrator must inspect the live session:
   - Query `GET /session/{id}` or `GET /session/{id}/message` to inspect token generation and tool calls.
   - **Progressing:** If tokens are actively flowing and constructive work is progressing, extend the timer window.
   - **Stalled:** If token generation is dead, or the agent is spinning in an unresolvable tool retry loop or orphaned subagent wait, only then terminate the attempt.
3. **Mandatory Zombie Cleanup:** When an attempt is halted, timed out, or interrupted, the harness (`delegate.py`) and orchestrator MUST issue an explicit `POST /session/{id}/abort` frame to the OpenCode REST port. Never allow orphaned subagent loops to churn GPU silicon after client disconnects.

#### 5. The Story Owner Tag & Anti-Bypass Guard
1. **Mandatory Owner Tag in Sprint Stories:** Every story defined in `SPRINT_PLAN_*.md` MUST specify an explicit `Assigned Owner:` tag:
   - `[SWARM:LOCAL]`: Story is assigned to local silicon execution via `delegate.py` with up to 3 diagnostic remediation rounds on local silicon.
   - `[SWARM:CLOUD]`: Story is assigned to cloud swarm burst via `delegate.py` directly, skipping local retries.
   - `[AGY:PRIMARY]`: Story is architectural, diagnostic, or governance work reserved for the primary orchestrator.
2. **Anti-Bypass Invariant:** When a story is tagged `[SWARM:*]`, the primary agent (AGY) is **strictly forbidden from directly modifying the story's target codebase files** without first executing delegation attempts via `delegate.py` (including all 3 local diagnostic rounds for `[SWARM:LOCAL]`).
3. **Escalation Record Required:** AGY direct code takeover (`[AGY:TAKEOVER]`) is only permissible after the assigned swarm tier (and its required diagnostic retries) has executed, failed, and logged an explicit diagnostic post-mortem in the sprint report. Direct coding on swarm-tagged stories without prior delegation attempts is a high-severity operational violation.

#### 6. Sovereign Local Silicon Topology Invariant (KENDER -> Air)
1. **The Sovereign Conductor & Leaf Worker Pattern:**
   `[SWARM:LOCAL]` execution MUST strictly adhere to the canonical bicameral silicon topology:
   - **Conductor (Root Dispatch):** Node KENDER (Windows RTX 4090 Ollama: `qwen3-14b-16k:latest` / `Atlas`). Receives the sprint story, conducts the 4-stage cascade, and dispatches bounded leaf tasks.
   - **Leaf Worker (Surgical Patching):** Node Brain (macOS M5 Air MLX: `mlx-community--Qwen3.5-9B-4bit` / `Sisyphus-Junior` or `Daedalus`). Receives spoon-fed 4-anchor tasks from Atlas, applies atomic `clara-dna_safe_patch` edits, and is strictly forbidden from delegating further (`task: deny`).
   - **Verifier (Execution & Lint Runner):** Node KENDER (Windows RTX 4090 / `Momus`). Executes verification commands and digests tracebacks back to Atlas.
2. **Topology Deviation Invariant:** Any inversion or deviation from this pattern (e.g., M5 Air attempting root orchestration, bypassing Node KENDER, or leaf workers spawning child subagents) constitutes an immediate operational failure. `delegate.py` and diagnostic monitors MUST enforce this check and fail immediately upon deviation.

#### 7. Post-Sprint Adversarial Oracle Sweep Gate (BKM-061)
1. **Mandatory Post-Sprint Closeout Sweep:** Before any sprint is marked `COMPLETED` or certified, the orchestrator MUST invoke the **Dual Adversarial Oracle Sweep** defined in **[BKM-061]**:
   - **Oracle 1 (Architecture & Invariants):** Audits threshold math, schema consistency, vector boundaries, and zero-work invariants.
   - **Oracle 2 (Side Effects & Blast Radius):** Audits port/socket contention, background daemon lifecycles, and backwards compatibility shims.
2. **Glaring Issue Remediation Gate:** If oracles discover glaring deficiencies or hidden "Green Lies", the orchestrator MUST fix and certify all glaring issues before publishing the final Work Completion Report ([BKM-007]).

---

## BKM-052: Sovereign Driver Protocol (Stateless Serialized Delegation for Fallback LLMs)
**Feature Anchor:** `[FEAT-530]` / `[BKM-052]`  
**Domain:** External Orchestration Fallback, Token Quota Exhaustion & Headless Dispatch  
**Status:** ACTIVE / MANDATORY  

#### 1. The Principle
When the primary orchestrator (AGY / Gemini CLI) exhausts its token quota or encounters severe rate-limiting, an alternative driver LLM (such as GPT-4o / Claude / DeepSeek via external CLI or Web UI) must be able to drive the sprint pipeline without attempting to manually write code, debug ASTs, or re-architect the system. The driver acts **strictly as a headless execution sequencer** for `delegate.py`.

#### 2. The Invariant Rules
1. **No Direct Code Generation:** The fallback driver is FORBIDDEN from generating code diffs or writing implementation files directly.
2. **No Human Docs:** Treat sprint documents on disk as executable instruction sets.
3. **Serialized Dispatch Only:** Dispatches MUST be strictly serialized. The driver invokes exactly ONE story at a time and blocks until `delegate.py` exits.
4. **Zero Self-Correction Loops:** If `delegate.py` returns a non-zero exit code (failure, blocker, or timeout), the driver does NOT attempt to rewrite the code. It executes the Tri-Loop remediation ladder (`--local-only` $\rightarrow$ `--cloud-only` $\rightarrow$ surface blocker to user).

#### 3. The 3-Step Driver Execution Loop

```
┌────────────────────────────────────────────────────────────┐
│ Step 1: Ingest Sprint Document Pointer                     │
│ Read SPRINT_PLAN_SPR_XX_0.md for story list & targets.     │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│ Step 2: Execute Headless Delegation via Bash               │
│ Invoke delegate.py for Story N:                            │
│   HomeLabAI/.venv/bin/python3 HomeLabAI/src/tests/delegate.py \
│     --sprint <S> --story <N> --title "<Title>"             │
│     --reference <sprint_plan_path>                         │
│     --target <target_file> --mode execute                  │
│     --details "Execute Story N in <sprint_plan_path>..."   │
│     --local-only                                           │
└─────────────────────────────┬──────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
      [Exit Code 0 (PASS)]        [Exit Code != 0 (FAIL)]
                │                           │
                ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ Step 3A: Git Commit Story │   │ Step 3B: Cloud Fallback   │
│ • git add <target_files>  │   │ Retry once with           │
│ • git commit -m "..."     │   │ `--cloud-only`. If fail,  │
│ • Proceed to Story N+1    │   │ report blocker & HALT.    │
└───────────────────────────┘   └───────────────────────────┘
```

#### 4. The Minimal Driver Prompt Template (For External GPT / Web Prompts)
When pasting instructions into an external LLM (e.g. ChatGPT / Claude) to drive the lab:

```text
You are the Federated Lab Delegation Driver (BKM-052).
Your ONLY task is to sequentially delegate stories in `Portfolio_Dev/SPRINT_PLAN_SPR_XX_0.md` using `delegate.py`.
DO NOT write code or generate file diffs yourself.

For each story:
1. Run:
   HomeLabAI/.venv/bin/python3 HomeLabAI/src/tests/delegate.py --sprint <S> --story <N> --title "<Title>" --reference Portfolio_Dev/SPRINT_PLAN_SPR_XX_0.md --target <target_path> --mode execute --details "Execute Story <N> in Portfolio_Dev/SPRINT_PLAN_SPR_XX_0.md (Section: Story <N>). Follow the 4-anchor specification in that section to modify target file using clara-dna_safe_patch. Verify with pytest." --local-only
2. If exit code is 0: Run `git add <target_files> && git commit -m "feat: complete Story <N>"` and advance to the next story.
3. If exit code is non-zero: Re-run with `--cloud-only`. If that fails, HALT and report the blocker.
```

---

## BKM-053: Multi-Remote Secondary Git Mirror & Cloud Redundancy Protocol
**Feature Anchor:** `[BKM-053]`  
**Domain:** Disaster Recovery, Cloud Redundancy & Sovereign Git Transport  
**Status:** DESIGN / BACKLOG  

### 1. Operational Mandate
To protect the 18-year engineering archive, systemd operational ledgers, and agentic codebases against single-platform outages, credential suspensions, or cloud service revocations, all federated lab repositories (`Dev_Lab`, `Portfolio_Dev`, `HomeLabAI`) MUST maintain dual-push secondary Git transport remotes alongside primary origins (GitLab/GitHub).

### 2. Implementation Mechanism
Configure dual-push Git remote targets via Git configuration:
```bash
git remote set-url --add --push origin <primary-origin-url>
git remote set-url --add --push origin <secondary-mirror-url>
```
When manual syncs or authorized replication scripts execute `git push origin <branch>`, Git automatically distributes commits synchronously to both hosting endpoints without introducing manual workflow steps.

---

## BKM-054: Zero In-Process PyTorch on Orchestrator Host (Precomputed & Offloaded Embeddings Law)
**Feature Anchor:** `[FEAT-567]` / `[BKM-054]`  
**Domain:** Memory Guard, System Stability & Zero-Torch Orchestration Architecture  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
The orchestrator host (`z87-Linux`) has a strict 16GB physical RAM ceiling shared with running browser sessions, Xorg, VS Code / Antigravity CLI, system daemons, and background monitors. Loading PyTorch (`import torch`), CUDA libraries, or `SentenceTransformer` directly inside the orchestrator's Python process consumes 2.5GB to 4.5GB of unpageable RSS, rapidly triggering Linux OOM killer reboots or silent Xorg desktop session resets during active sprints.

### 2. The Invariant Rules
1. **Zero In-Process PyTorch:** All orchestrator Python scripts (including fast test suites, CLI tools, and background sync workers) are STRICTLY FORBIDDEN from importing `torch`, `torchvision`, or `sentence_transformers` in-process on `z87-Linux`.
2. **Dual Path for Embeddings:**
   - **Path A (Remote Offload):** Query silicon endpoints (e.g. M5 Air via REST on port 8000 or local vLLM on port 8088) to generate dense embeddings.
   - **Path B (Precomputed Embeddings):** Use pre-generated vector caches (`.npy` or `.json` fixtures) stored in the repo or ChromaDB collections for similarity lookups and dedup testing.
3. **AST Lint Guard:** Automated linters and pre-commit hooks (`FEAT-567`) must actively audit orchestrator code to reject any PR or commit introducing direct `torch` imports.

---

## BKM-055: The Decoupled Artifact Law (Cache-First ASTs & Independent Compilation)
**Feature Anchor:** `[FEAT-581]` / `[FEAT-582]` / `[FEAT-588]` / `[BKM-055]`  
**Domain:** Document Architecture, AST Provenance & Deterministic Synthesis  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
Runtime execution (such as vector databases, embeddings, and model daemons) is volatile, latency-prone, and ephemeral. Artifacts of record (technical papers, engineering resumes, architectural specs) must remain decoupled, immutable, and self-contained. An interactive document editor or compiler must never stall on network requests or depend on live database daemons to hydrate its view or generate static outputs.

### 2. The Invariant Rules
1. **Tri-Phase Document Lifecycle (Discover $\rightarrow$ Curate $\rightarrow$ Generate):**
   - **Phase 1: Discover (On-Demand Vector Query):** ChromaDB lookups across DNA collections (`PHL`, `WIS`, `FEAT`, `DISC`, `paper_dna_<slug>`) occur strictly upon explicit user trigger (e.g. document import or objective paste). Discovered matches are deposited directly into the document AST's `_candidate_pool[]`.
   - **Phase 2: Curate (Interactive Waterline):** The author or combinatorial optimizer promotes candidates "Above Water" into the tier's `bone_collection[]` (Root/Section) or `citations[]` (Paragraph/Bullet). Changes are saved directly into the paper's JSON AST.
   - **Phase 3: Generate (Deterministic AST Compilation):** Document compilers (`build_writer.py`, LaTeX engines) assemble outputs strictly from the cached AST `bone_collection[]` and verbatim text nodes with zero runtime database connectivity.
2. **Multi-Tier Hierarchical AST Caching:**
   - Every level of the document AST (Paper Root, Section, Paragraph/Bullet) must maintain its own dedicated `bone_collection[]` (or `citations[]`) and `_candidate_pool[]` arrays.
   - Opening, navigating, or collapsing sections in `writer.html` must operate client-side with 0ms latency without making REST calls to ChromaDB.
3. **Anti-Embellishment Functional Decoupling:**
   - Machine intelligence applied to technical resumes or publications is strictly constrained to **combinatorial judgment** (relevance scoring, auto-pruning recommendations, and evidence chip attachment).
   - Generative hallucination or prose embellishment is strictly forbidden; all synthesized outputs must assemble verbatim human bullet points and tangible repository citations.

---

## BKM-057: Config-to-Daemon Freshness Synchronization Protocol
**Feature Anchor:** `[FEAT-553]` / `[BKM-057]`  
**Domain:** Infrastructure, Service Daemons & Delegation Pre-Flight  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
Editing configuration files on disk (`opencode.json`, `infrastructure.json`, `oh-my-openagent.json`) does not alter the in-memory state of running background services. Running workloads against a stale background daemon silently reproduces old bugs, ignores updated context boundaries, and wastes tokens on dead execution paths.

### 2. The Invariant Rules
1. **Timestamp Comparison Before Dispatch:** Before executing swarm delegations, the launcher (`delegate.py`) must inspect the running process start time via systemd (`/proc/<pid>` start time) and compare it against the latest `os.path.getmtime` of all active configuration files.
2. **Automated Zero-Downtime Hot Restart:** If any configuration file is newer than the service start time, `delegate.py` must automatically trigger a clean service restart (`systemctl --user restart opencode-core.service`), verify port health, and log `[STALE_SERVICE_SYNC]` before dispatching.
3. **No Blind Retries on Unrefreshed Daemons:** Never re-attempt failed delegations after config edits without confirming daemon recreation.

---

## BKM-058: Communication & User-First Acknowledgment Protocol
**Feature Anchor:** `[BKM-058]` / `[AGENTS.md Law 6]`  
**Domain:** Agent Human-Interaction, Operational Transparency  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
Autonomous agent speed must never come at the expense of operator transparency. When an operator asks a question, raises a concern, or points out a system discrepancy, executing silent automated fixes behind the scenes creates confusion and prevents the operator from validating their insight.

### 2. The Invariant Rules
1. **Acknowledge in Text First:** Always answer, validate, and explain the user's specific observation in the visible text response *before* executing code fixes or triggering background state transitions.
2. **Explicit Attribution:** Clearly state the root cause and confirm the validity of the user's insight so the human operator knows their feedback made a concrete difference.
3. **No Silent Mutations:** Background modifications must be explicitly summarized with actionable rationale.

---

## BKM-060: Federated DNA Taxonomy & Horizontal Re-Bucketing Mandate
**Feature Anchor:** `[FEAT-582]` / `[FEAT-585]` / `[BKM-060]`  
**Domain:** Memory Architecture, DNA Curation, JITC Vector Grounding  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
Federated Lab memory is categorized into distinct, peer-level **DNA Buckets** that answer specific cognitive queries. Domains are equal horizontal peers, not a hierarchical ladder. Memory items that drift or are discovered in the wrong container must be horizontally migrated (re-bucketed) to preserve semantic retrieval precision across CLaRaDB port 8001.

### 2. The Universal Taxonomy Matrix (How vs. Why vs. What vs. When)
| Bucket | Prefix | Cognitive Purpose | Primary Question | Source of Record |
| :--- | :--- | :--- | :--- | :--- |
| **Philosophy** | `PHL-xxx` | Conceptual Worldviews & Invariant Epistemology | **WHY (First Principle)** | `philosophy_data.json` $\rightarrow$ `philosophy_dna` |
| **Wisdom** | `WIS-xxx` | Practical Lessons, War Stories & Failure Scars | **WHY (Empirical)** | `stories.html` $\rightarrow$ `wisdom_data.json` $\rightarrow$ `philosophy_dna` |
| **Protocols** | `BKM-xxx` | Prescriptive Rules & Actionable Directives | **HOW (Mandate)** | `Protocols.md` $\rightarrow$ `behavioral_dna` |
| **Features** | `FEAT-xxx` | Registered Capabilities & Architectural Specs | **WHAT (Mechanics)** | `FeatureTracker.md` $\rightarrow$ `feature_dna` |
| **Vibes** | `VIBE-xxx` | Behavioral Persona & Conversational Tonality | **WHO (Tone)** | `FeatureTracker.md` $\rightarrow$ `feature_dna` |
| **Discoveries**| `DISC-xxx` | Distillation Insights & Subconscious Epiphanies | **WHAT (Insight)** | `discovery` collection $\rightarrow$ `DISC` ledger |
| **Sprint DNA** | `SPR-xxx` | Active Sprint Plans, Story Cards & Decoupled ASTs | **WHEN (Active)** | `SPRINT_PLAN_*.md` $\rightarrow$ `sprint_dna` |
| **Reverse DNA**| `RDNA-xxx` | Pre-Processed Question Space & HyDE Bypass | **WHEN / ASK** | `rdna_questions.json` $\rightarrow$ `rdna` |
| **Artifacts** | `ART-xxx` | External Google Drive / Doc Links & Assets | **WHERE (Asset)** | `artifact_vault` collection |

### 3. The Invariant Rules
1. **Separation of Bucket vs. Topic:** Never confuse the **DNA Bucket** (e.g. `BKM`) with the **Subject Topic Tag** (e.g. `#systems_architecture`, `#security`).
2. **Horizontal Re-Bucketing:** If an item is discovered in the wrong container (e.g. a raw discovery that is actually an operational mandate), it must be horizontally migrated to its rightful bucket with bidirectional `explicit_links` preserved.
3. **JITC Retrieval Law:** Agents must query specific taxonomy buckets on-demand via `get_protocol(bkm_id="BKM-xxx")` or `query_dna(collection="...")` rather than loading global taxonomy tables into primary agent prompt context.

---

## BKM-061: Multi-Tier Swarm Audit & Adversarial Oracle Protocol
**Feature Anchor:** `[FEAT-477]` / `[FEAT-582]` / `[BKM-061]`  
**Domain:** Codebase Health, Verification Rigor, Pre/Mid/Post-Sprint Oracle Audits  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle
A single primary agent or developer working across a large codebase suffers from context dilution, fatigue, and author bias—frequently missing subtle edge-case traps, stale lockouts, hidden zero-work escapes ("Green Lies"), and unhandled error returns. The **Adversarial Oracle** is an independent, highly critical reasoning subagent tasked specifically with finding flaws, side effects, and violations of invariants before changes are certified.

### 2. When to Deploy Oracles (The 3 Oracle Horizons)
1. **Pre-Sprint Architecture Oracle:** Invoked during Design Studio ([BKM-005]) to audit proposed sprint plans, schema designs, REST endpoints, and mathematical bounds before code is written.
2. **Mid-Flight Sanity Oracle:** Invoked after complex refactors or multi-adapter changes to verify memory safety, thread safety, and interface compatibility.
3. **Post-Sprint Adversarial Sweep ([BKM-049]):** Mandatory closeout audit executed across the full Git diff. The sweep deploys specialized oracles to rigorously probe:
   * **Oracle 1 (Architecture & Invariants):** Audits threshold math, schema consistency, vector boundaries, and zero-work invariants ([BKM-062]).
   * **Oracle 2 (Side Effects & Blast Radius):** Audits port/socket contention, background daemon lifecycles, and backwards compatibility shims.

### 3. Oracle Prompting & Anti-Sycophancy Best Practices
* **Explicit Adversarial Mandate:** Never ask an oracle "Does this look good?" or "Is this ready?" Instead, explicitly instruct the oracle: *"Your goal is to uncover hidden flaws, failure modes, race conditions, and invariant violations. Assume there are bugs."*
* **Specialized Decoupled Roles:** Spawn discrete oracles with narrow, non-overlapping concerns (e.g. Invariants vs. Blast Radius vs. Failure Modes).
* **Model Tiering:** Always select deep reasoning / `pro` model tiers for Oracles so they can explore wide dependency trees and long context reasoning.
* **The Glaring Issues Output Contract:** Require Oracles to categorize findings into **Glaring Issues** (must fix before sprint signoff) vs. **Latent / Backlog Items**.

### 4. The 4-Tier Swarm Audit Anatomy
1. **Tier 1 — Parallel Specialized Swarm (4-Way Subagent Dispatches):**
   * *Pipeline & Daemon Auditor:* Audits background jobs, systemd units, execution order, and stale lockout flags (`nightly_forge.py`, `nightly_lora_training.py`).
   * *Backend & Router Auditor:* Audits REST endpoints, database atomicity, ID allocation counters, and disk vs. DB serialization (`router.py`, `draft_decomposer.py`).
   * *Frontend & UX Flow Auditor:* Audits UI event reactivity, DOM pills, client-side data binding, and build script linkages (`dna_forge_build.py`, `writer.html`).
   * *Schema & Invariant Auditor:* Audits JSON data completeness across legacy and newly added entries, git pre-commit hooks, and vector DB sync idempotency (`*.json`, `.git/hooks/pre-commit`).
2. **Tier 2 — Synthesized Deficiency Matrix:**
   * Aggregate all subagent findings into a ranked deficiency matrix (`CRITICAL_BREAKAGES`, `ID_COLLISIONS`, `STALE_LOCKOUTS`, `ORPHAN_CODE`, `UX_STALE_STATES`).
3. **Tier 3 — Dual Adversarial Oracle Review:**
   * *Architecture & Invariants Oracle:* Evaluates mathematical bounds, vector thresholds (e.g. HyDE bypass cosine distance), schema invariants, and graph link integrity.
   * *Side Effects & Blast Radius Oracle:* Evaluates operational collisions (e.g. VRAM concurrency, process isolation), backwards compatibility shims, and deprecation blast radii.
4. **Tier 4 — Live Invariant Certification (BKM-024):**
   * Execute deterministic roundtrip unit tests (`test_dna_roundtrip_consistency.py`).
   * Verify all active daemons match local Git HEAD.

---

## BKM-062: Fail-Fast & Explicit Failure Propagation Mandate
**Feature Anchor:** `[FEAT-607]` / `[FEAT-608]` / `[LAB-110]` / `[BKM-062]`  
**Colloquial Alias:** "Green-Lie Prevention"  
**Domain:** Operational Rigor, Lab Accountability, Telemetry Invariants, Fail-Fast Design Pattern  
**Status:** ACTIVE / MANDATORY  

### 1. The Principle (Positive Framing)
Every telemetry-emitting function MUST produce verifiable, non-zero, live-sourced output — or return an explicit `FAIL` with a descriptive error. Errors and failures must propagate up through call chains explicitly; they must never be swallowed, absorbed into a silent `except` block, or replaced with a hardcoded success stub.

**The Fail-Fast Design Pattern Applied:** Surface errors at the earliest possible point. Never recover silently to a plausible-looking success state. A system that lies green while broken is worse than one that fails loudly.

**Colloquial name — "The Green Lie":** A lab status or test step that reports exit code `0` or `ONLINE` while doing zero work (0 items processed, 0 tokens generated, 0 mutations certified, or silent exceptions caught and swallowed). Green status is strictly reserved for non-zero verifiable progress.

### 1b. JITC Hook Trigger Phrases (for ambient retrieval)
This BKM should be retrieved during coding moments involving:
- Writing a `try/except` block in a telemetry or pipeline function
- Adding a fallback return value in an error branch (e.g. `return {"status": "ok"}`)
- Writing any function that emits `turns_synthesized`, `items_refined`, `status`, or health metrics
- Adding a hardcoded dict as a return value on exception
- Writing silent exception swallowing (`except Exception: pass`)
- Writing health-check probes or nightly sweep stages
- Adding `time.sleep()` near subprocess calls without explicit error propagation

### 2. The Invariant Rules
1. **Zero-Work Exit Is A Fatal Defect:** Any pipeline stage or daemon sweep that completes with exit code 0 but records 0 items, 0 tokens, or 0 steps when work was queued or expected MUST be classified as `FAILED` (RED).
2. **Tri-State Quantifiable Accountability:** All automated processes must be evaluated against explicit thresholds loaded from `HomeLabAI/config/lab_accountability_thresholds.json`:
   - `GREEN (PASS)`: Verifiable non-zero progress meeting or exceeding target metrics.
   - `AMBER (DEGRADED)`: Partial throughput or elevated latency within acceptable fallback margins.
   - `RED (CRITICAL)`: Silent passes, zero items processed, fatal crashes, unhandled timeouts, or persona mute errors.
3. **The Green-Lie Sentry Mandate:** If individual daemons (e.g., Foyer, vLLM, Deep Thought) report `ONLINE`, but synthetic morning round table probes or nightly sweeps fail, the dashboard (`status.html`) MUST display a prominent `DISCREPANCY ALERT` banner. Never allow green daemon indicators to mask broken conversational circuits.
4. **Authoritative Nightly Digest:** The 11-stage nightly sweep must emit a consolidated `daily_accountability_digest.json` and a formatted `[+] ACCOUNTABILITY DIGEST` entry in the interleaved system log, recording exact per-stage metrics, overall status, and fallback justifications.
5. **Zero-Mock Policy for Live Validation (BKM-024):** Synthetic morning probes and health checks must run live end-to-end HTTP/REST requests against running silicon engines (Foyer :8765, vLLM :8088, M5 Air :8000). Mocks are strictly forbidden for live certification.



