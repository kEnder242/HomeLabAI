# Operational Protocols: Acme Lab

> [!IMPORTANT]
> **IMMUTABILITY RULE:** Protocols in this document can ONLY be added. They must NEVER be refactored, slimmed down, or removed unless explicitly requested by the Lead Engineer.

## BKM-001: The Cold-Start Protocol (Hardware & Service)
**Objective**: Restore the Lab environment from a powered-off or crashed state.

0.  **Orientation (Bootstrap)**:
    *   Refer to the top-level **[README.md](../../README.md)** for the primary navigational hub and global project context.

1.  **Hardware/Driver Audit**:
    *   Execute `nvidia-smi`.
    *   **Success**: Driver version (e.g., 570+) and CUDA (e.g., 12.8) reported.
    *   **Failure**: If "could not communicate with driver," run `sudo apt install --reinstall nvidia-driver-570 nvidia-dkms-570` and `sudo update-initramfs -u`, then reboot.

2.  **Orchestrator Liveliness**:
    *   Execute `sudo systemctl status lab-attendant.service`.
    *   **Action**: If not running, `sudo systemctl restart lab-attendant.service`.
    *   **Verification**: `curl http://localhost:9999/status` should return JSON.

3.  **Lab Server Ignition**:
    *   **Stable Path (No Mic)**:
        `curl -X POST http://localhost:9999/start -H "Content-Type: application/json" -d '{"mode": "SERVICE_UNATTENDED", "disable_ear": true}'`
    *   **Experimental Path (With Mic)**:
        `curl -X POST http://localhost:9999/start -H "Content-Type: application/json" -d '{"mode": "SERVICE_UNATTENDED", "disable_ear": false}'`

4.  **Uplink Verification**:
    *   `tail -f HomeLabAI/server.log` (Watch for `[READY] Lab is Open`).
    *   Handshake via `intercom.py`.

## BKM-002: The Montana Protocol (Logger Authority)
**Objective**: Prevent third-party ML libraries from hijacking the diagnostic stream.

*   All `acme_lab.py` logging must go to `sys.stderr`.
*   Call `reclaim_logger()` immediately after heavy imports (NeMo, ChromaDB).
*   `lab_attendant.py` is the authority for file redirection (`stderr -> server.log`).

## BKM-003: Resident Sequencing
**Objective**: Prevent MCP initialization deadlocks.

*   Residents must be loaded **sequentially** with a minimum 2-second sleep between `archive` -> `pinky` -> `brain`.
*   Avoid `asyncio.gather` for initial MCP handshakes on resource-constrained hosts.

## BKM-004: The "Discuss with me" Protocol (QQ / Quick Question)
**Objective**: Prevent state drift and hardware locks when automated recovery fails.

1.  **Shorthand (QQ)**: If the user says "QQ: [Question]", the Agent must provide a concise, direct answer without implementation details, debug logs, or deep implementation dives.
2.  **Halt Conditions**:
    *   Encountering a "Zombie" process (orphaned PID) that ignores `pkill -9`.
    *   Encountering a `torch.OutOfMemoryError` during a "Heads Down" sprint.
    *   NVIDIA driver reporting "Communication Error" or `nvidia-smi` hanging.
3.  **Action**: HALT all implementation.
4.  **Reporting**: Present the hardware state (PID, VRAM usage, driver logs) to the Lead Engineer.
5.  **Resolution**: WAIT for explicit approval before attempting `sudo` level interventions or system reboots.
6.  **Persistence of Halt**: Informational or retrospective queries (e.g., "Tell me what you did", "Explain that log") do NOT signal a resumption of work. The Agent MUST remain in the **HALT** state until the user provides an explicit execution directive (e.g., "Fix it", "Proceed", "Apply").

## BKM-005: The Design Studio (Greenlight before Silicon Change)
**Objective**: Ensure alignment on naming, architecture, and persona before committing code.

1.  **The Pitch**: Agent summarizes the goal in one sentence.
2.  **The Options**: Agent presents 2-3 implementation paths (e.g., Simple, Robust, Experimental).
3.  **The Naming Ceremony**: Explicit agreement on Nouns (Folders, DB Collections) and Verbs (Tool Names).
4.  **The Contract**: User gives "Greenlight" to a specific path.

## BKM-006: Heads Down / AFK Continuity (Safety Valve Logic)
**Objective**: Enable autonomous agent sprints while protecting hardware resources.

1.  **Trigger**: User gives a "Heads Down" mandate or says "Going AFK" (or just "AFK").
2.  **Continuity**: The Agent works sequentially through `ProjectStatus.md`, skipping blocked tasks.
3.  **Safety Valve**: The Lab server MUST have `--afk-timeout 60` active. This ensures that if the Agent/User connection drops, the GPU is not left idling.
4.  **Silence**: No incremental status updates; the Agent only "pops up" for BKM-004 Halt Conditions.
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


## BKM-010: Silicon Co-Pilot (Interactive Mode)
**Objective**: Maintain diagnostic fidelity during live user/agent collaboration.
**Trigger**: "Interactive Demo", "Co-Pilot Mode", or live debugging requests.

1.  **The Test Plan**: Present a clear plan (What to test, expected outcome) before launching.
2.  **Versioning**: Agent MUST bump the system VERSION (in acme_lab.py) if any client/server logic changed to prevent "Old Code" traps.
3.  **Execute (Blocking)**: Agent runs the co-pilot script and WAITS. 
    *   *Timeout*: Tool calls must automatically time out after 300s to prevent Agent lockup.
4.  **Verbal Feedback**: Actively mine logs for user notes (e.g., "Pinky, note that X is broken") received during the session.
5.  **Post-Mortem**: Immediately update `ProjectStatus.md` with findings from both logs and user feedback.

## BKM-007: The "Heads Up" Report (High-Fidelity Debrief)
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Verbosity**: The report must be detailed and verbose (reversing minimalist CLI compression).
3.  **Content**:
    *   Summary of all completed items.
    *   Implications: Impact on VRAM, latency, and security.
    *   The "Path Backwards": Rollback steps if the new silicon is unstable.
4.  **Verification**: Re-verify all services (Ollama, vLLM, Intercom) before handing back control.
