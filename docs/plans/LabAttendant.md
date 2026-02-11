# Lab Attendant Orchestration Server (Proposed Architecture)

## I. Problem Statement
The current manual process for managing the `acme_lab.py` server (starting, stopping, monitoring logs, ensuring clean state) is high-friction and prone to errors. Issues include:
*   Difficulty in reliably launching and backgrounding `acme_lab.py` (e.g., `nohup` redirection inconsistencies).
*   Lack of real-time, programmatic visibility into the server's boot process and status.
*   Persistent "zombie" processes or stale lock files requiring manual intervention.
*   Debugging cycles are slow due to unclear diagnostic output.
*   Inability for the Gemini CLI agent to reliably manage the server's lifecycle due to `run_shell_command` limitations (e.g., `pkill` causing session interruptions).

## II. Proposed Solution: The `lab_attendant.py` Orchestrator

The `lab_attendant.py` is a new, lightweight Python application designed to act as a dedicated orchestration server for the main `acme_lab.py` server. It provides a stable API for managing the Lab's lifecycle, status, and logs.

### A. Core Responsibilities
1.  **Process Lifecycle Management**:
    *   **`start_lab(mode: str)`**: Launches `acme_lab.py` in the specified mode (e.g., `DEBUG_BRAIN`, `SERVICE_UNATTENDED`) as a subprocess. Captures and tracks its PID.
    *   **`stop_lab()`**: Gracefully terminates the `acme_lab.py` process (SIGTERM, then SIGKILL if needed).
    *   **`restart_lab(mode: str)`**: Combines `stop_lab()` and `start_lab()`.
    *   **`cleanup()`**: Performs pre-flight cleanup (removes `server.log`, `round_table.lock`).
2.  **Real-time Status Monitoring**:
    *   **`get_status()`**: Provides a JSON endpoint reporting:
        *   `acme_lab.py` PID (if running).
        *   Status of port 8765 (LISTENING/CLOSED).
        *   Last few lines of `server.log` (or full log via `/logs` endpoint).
        *   Current VRAM usage (via `nvidia-smi` when GPU is active).
        *   Indication of "READY" state based on log parsing.
        *   `round_table.lock` status.
3.  **Log Stream & Archiving**:
    *   **`get_logs(lines: int = N)`**: Retrieves the latest N lines of `server.log`.
    *   **`tail_logs()`**: Provides a WebSocket endpoint for live log streaming (future enhancement).
    *   Archives logs upon `stop_lab()` or `restart_lab()`.
4.  **Decoupling from Agent Environment**:
    *   Runs as its own daemon, insulating the `acme_lab.py` lifecycle from the CLI agent's `run_shell_command` limitations.
    *   Eliminates the need for `nohup` for `acme_lab.py`.

### B. Technical Details
*   **Technology**: Lightweight Python `aiohttp.web` server.
*   **Port**: Dedicated, separate port (e.g., 9999) to avoid conflicts with `acme_lab.py`.
*   **No Heavy Imports**: `lab_attendant.py` will explicitly avoid importing `chromadb`, `nemo`, `sentence_transformers`, etc., ensuring fast startup and minimal resource footprint.
*   **Communication**: Agent interacts with `lab_attendant.py` via HTTP/REST endpoints.

### C. Benefits
*   **Reliable Lifecycle Management**: Consistent starting and stopping of the Lab server.
*   **Enhanced Observability**: Programmatic access to server status and logs, enabling smarter polling by the agent.
*   **Faster Debugging**: Clearer feedback loops, allowing the agent to react intelligently to server states.
*   **Isolation**: Prevents agent execution environment issues (like `pkill` interrupting sessions) from affecting the Lab server.
*   **Foundation for Automation**: Provides a robust API for future integration tests and automated deployments.

## III. Initial Implementation (Phase 1)
For the first trial round, `lab_attendant.py` will implement:
*   `GET /status` (minimal: PID, port 8765 status, last log line, Lab status).
*   `POST /start` (starts `acme_lab.py` in specified mode).
*   `POST /stop` (stops `acme_lab.py`).
*   `POST /cleanup` (removes logs and lock file).
*   `GET /logs` (returns full `server.log` content).

This will immediately address the core management and observability challenges.
