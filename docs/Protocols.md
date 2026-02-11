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
