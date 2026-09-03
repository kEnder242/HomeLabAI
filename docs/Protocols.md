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

## BKM-024: Validation-Aware Synchronization & Live Integration
**Objective**: Ensure the physical Lab state and running daemon processes match active sprint code before testing.

1.  **Sync-Gate**: Before running any `[LIVE FIRE]`, `[SHAKEDOWN]`, or integration test (`test_integration_*.py`), the Agent MUST check service liveness (`curl http://127.0.0.1:8000/status` or `lab_heartbeat`).
2.  **Mandatory Service Reload**: If any file in `src/logic/`, `src/nodes/`, or `src/forge/` was edited during the session, the Agent MUST execute `sudo systemctl restart lab-attendant.service` to flush cached Python processes before executing tests.
3.  **State Trust**: Do not assume background processes persisted cleanly across git commits or code refactors. Re-verify liveness and run live integration tests after every service restart.

### BKM-020: High-Fidelity Sprint Documentation (Intent Preservation)
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
**Objective**: Establish a high-efficiency, token-optimized delegation workflow between the Strategic Orchestrator (**Antigravity / Gemini**) and the tactical developer swarm (**OpenAgent**).

1. **REST Dispatch Law**:
   * All task dispatches to OpenAgent MUST use the formalized Python launcher [**src/tests/delegate.py**](https://github.com/kEnder242/HomeLabAI/blob/main/src/tests/delegate.py) (`POST http://127.0.0.1:4097/session/<id>/message`).
   * Direct invocation of `opencode run --attach` is **strictly forbidden** (it is a blocking TUI that hangs indefinitely when port 4096 is idle).
   * Dispatch syntax:
     ```bash
     python3 src/tests/delegate.py --sprint <S> --story <N> --title "<Title>" --reference "<plan_path>" --target "<file_paths>" --details "<spec>" --dir "<workspace_dir>" --mode execute
     ```

2. **The Two-Tier Payload Standard ([BKM-043])**:
   Every delegation prompt dispatched to OpenAgent MUST be structured in two tiers to provide maximum architectural coherence with zero prompt wandering:
   * **Tier 1 (Global Situational Awareness)**: The overarching Sprint Theme, Executive Summary, and Story Matrix (~20–30 lines). Tells the agent where its piece fits in the machine.
   * **Tier 2 (Bounded Story Contract)**: The 4-Anchor Prompt Standard (`Grep-Stable Code Anchor`, `Import Anchor`, `Path Anchor`, `Surgical Delta & Concrete Test Assertions`). Strictly binds the agent's write tools to assigned target files.
   * **Sprint Doc Pointer**: Pointers to the active sprint plan on disk (e.g. `Portfolio_Dev/SPRINT_PLAN_SPR_65_0.md`) for deep context lookups without copy-paste truncation.

3. **Git Forensic Ownership Gate**:
   * Subagent workers edit files and run local test suites, but are **strictly prohibited from executing `git commit`**.
   * The Strategic Orchestrator audits `git diff`, verifies `pytest` output, and performs all git commits.

4. **The Tri-Loop Feedback & Remediation Engine**:
   * **In-Flight Handover Reflection**: `delegate.py` automatically extracts the subagent's `[HANDOVER REFLECTION]` directly from the in-memory completion chunk and prints it front-and-center in the terminal output, auto-storing friction in ICM (`errors-resolved`).
   * **The Tri-Loop Remediation Ladder**:
     - **Loop A (Fast In-Session Re-fire / Test Trace Remediation)**: If `pytest` or compiler execution fails, re-fire into the *same persistent session* (`--session-id`) passing the exact traceback snippet without cold-starting daemons.
     - **Loop B (Anti-Drift / Stub-Tightening Re-fire)**: If a subagent drifts into repository exploration or edits unassigned files, re-fire with an explicit line-range diff anchor and tightened scope.
     - **Loop C (Hard Blocker & Harness Escalation)**: If a subagent emits `[BLOCKER REPORT: <CATEGORY>]` or halts on an interactive popup / silent finish (`finish=unknown`), `delegate.py` immediately breaks out (Exit Code 2: `AWAITING_INPUT`), logs to `delegation_failures.log`, and yields to the Strategic Orchestrator / Human Driver via `--resume <session_id> --answer <choice>`. Never bypass a delegation harness failure to finish a sprint manually.

5. **Session Continuity & Context Re-use (`--session-id`)**:
   * For related stories within the same sprint phase (e.g., Phase 1: Stories 65.1 & 65.2), orchestrators should reuse persistent session IDs (`--session-id sprint-65`) to preserve warmed repo file trees, terminal test execution history, and recent diffs in OpenCode's working context.
   * **Circuit Breaker**: If a session exceeds 30+ tool calls or shows signs of hallucination/looping, the orchestrator terminates the session and creates a fresh session ID (`--session-id sprint-65-phase2`).

6. **The Mandatory Post-Delegation Intent & Omissions Audit**:
   * Before staging and committing any delegated story, the Strategic Orchestrator MUST conduct an explicit **Intent & Omissions Audit** beyond the literal `git diff`:
     1. **Contract Completeness**: Were all functional requirements in `--details` implemented, or did the subagent silently skip a secondary sub-clause?
     2. **Dead-Code & Inert Artifacts**: Did the code change leave inert variables or orphaned functions? Are they safely documented per minimal-edit discipline?
     3. **Boundary Integrity**: Did the subagent create or modify any files outside the assigned `--target` list?
     4. **Test Realism & Coverage**: Do the new tests genuinely assert the behavioral contract rather than mocking out the core logic?

> [!NOTE]
> For internal swarm topology, model tool-calling constraints (KENDER/Qwen3), OmO `task()` mechanics, and socket proxy architecture, refer to [**OPENAGENT_HANDOVER_PLAYBOOK.md**](../../Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md).

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
│     - Swarm Role: Layer 2 Orchestrator (Atlas) — absorbs broad sprint plans, global      │
│       state, and sequences task dependencies. Pure routing (NO CODE EDITS).              │
│                                                                                          │
│  2. Node Brain (Apple M5 Air 32GB Unified Memory / oMLX dflash):                         │
│     - Model: mlx-community--Qwen3.8-27B-4bit (15.2 GB resident).                         │
│     - Metal Memory Ceiling: iogpu.wired_limit_mb caps wired GPU memory at ~24.46 GB.     │
│       A 27B model prefilling > 4k tokens triggers immediate Metal allocation panic.      │
│     - Swarm Role: Layer 3 Fast Worker (Sisyphus-Junior) — bounded (< 1.5k tok) code     │
│       stub fill via clara-dna_safe_patch. Heavy search/tools disabled.                   │
│                                                                                          │
│  SWARM TOPOLOGY INVERSION LAW:                                                           │
│  - Broad Context (Tier 1 Sprint) MUST flow into 4090 Atlas (Flexible RAM ceiling).       │
│  - Narrow Contracts (Tier 2 AST Stubs) MUST flow into M5 Air Junior (Fast, strict cap).  │
│  - Violating this hierarchy by feeding 10k token plans to M5 Air blows the Metal limit;  │
│    forcing 4090 to execute code edits ties up the orchestrator on low-tier syntax.       │
│                                                                                          │
│  SCARS RETROSPECTIVE:                                                                    │
│  - Scar #1: Feeding broad sprint context directly to M5 Air 27B caused silent kernel     │
│    hangs when Metal prefill activation buffers exceeded wired unified memory limits.     │
│  - Scar #2: Atlas attempting direct file editing caused hallucinated imports; resolved   │
│    by hard-pinning Atlas permissions to edit:deny and task(category="unspecified-low").  │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## BKM-048: Just-in-Time (JIT) Context Interleaving & The "Fingertips" Protocol

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

### [BKM-051] Subagent MCP Tool Scoping & Context Ballast Protocol
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
```

---

### [BKM-049] Tri-Loop Story Delegation & Diagnostic Protocol
**Feature Anchor:** `[FEAT-522]` / `[BKM-049]`  
**Domain:** Swarm Delegation, Autonomous Subagent Execution & Harness Diagnostics  
**Status:** ACTIVE / MANDATORY  

#### 1. The Tri-Loop Law
1. **Three-Tier Escalation Ladder:** A story assigned to delegation executes through a strictly structured 3-tier escalation ladder:
   * **Attempt 1: Sovereign Local Silicon (`[SWARM:LOCAL]`)** — Windows RTX 4090 (Atlas) + macOS M5 Air (Junior). 100% private, sovereign execution.
   * **Attempt 2: Cloud Swarm (`[SWARM:CLOUD]`)** — OpenCode Cloud / OpenRouter / DeepSeek / Cohere. Burst capacity for complex reasoning when local models hit context or syntax boundaries.
   * **Attempt 3: Primary Agent (`[AGY:TAKEOVER]`)** — AGY executes direct AST implementation and architectural certification, preserving primary tokens.
2. **Never Blindly Retry:** A retry between tiers is strictly defined as an execution attempt preceded by root-cause diagnosis. Simply tweaking prompt wording without fixing underlying tool/permission mismatch is an invariant violation.
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
