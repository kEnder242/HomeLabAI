# Operational Protocols: Acme Lab

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

## BKM-004: The "Discuss with me" Protocol (Halt on Silicon Error)
**Objective**: Prevent state drift and hardware locks when automated recovery fails.

1.  **Halt Conditions**:
    *   Encountering a "Zombie" process (orphaned PID) that ignores `pkill -9`.
    *   Encountering a `torch.OutOfMemoryError` during a "Heads Down" sprint.
    *   NVIDIA driver reporting "Communication Error" or `nvidia-smi` hanging.
2.  **Action**: HALT all implementation.
3.  **Reporting**: Present the hardware state (PID, VRAM usage, driver logs) to the Lead Engineer.
4.  **Resolution**: WAIT for explicit approval before attempting `sudo` level interventions or system reboots.

## BKM-005: The Design Studio (Greenlight before Silicon Change)
**Objective**: Ensure alignment on naming, architecture, and persona before committing code.

1.  **The Pitch**: Agent summarizes the goal in one sentence.
2.  **The Options**: Agent presents 2-3 implementation paths (e.g., Simple, Robust, Experimental).
3.  **The Naming Ceremony**: Explicit agreement on Nouns (Folders, DB Collections) and Verbs (Tool Names).
4.  **The Contract**: User gives "Greenlight" to a specific path.

## BKM-006: Heads Down / AFK Continuity (Safety Valve Logic)
**Objective**: Enable autonomous agent sprints while protecting hardware resources.

1.  **Trigger**: User gives a "Heads Down" mandate or says "Going AFK."
2.  **Continuity**: The Agent works sequentially through `ProjectStatus.md`, skipping blocked tasks.
3.  **Safety Valve**: The Lab server MUST have `--afk-timeout 60` active. This ensures that if the Agent/User connection drops, the GPU is not left idling.
4.  **Silence**: No incremental status updates; the Agent only "pops up" for BKM-004 Halt Conditions.

## BKM-007: The "Heads Up" Report (High-Fidelity Debrief)
**Objective**: Restore technical context after a deep work cycle.

1.  **Trigger**: Conclusion of a "Heads Down" sprint.
2.  **Verbosity**: The report must be detailed and verbose (reversing minimalist CLI compression).
3.  **Content**:
    *   Summary of all completed items.
    *   Implications: Impact on VRAM, latency, and security.
    *   The "Path Backwards": Rollback steps if the new silicon is unstable.
4.  **Verification**: Re-verify all services (Ollama, vLLM, Intercom) before handing back control.
