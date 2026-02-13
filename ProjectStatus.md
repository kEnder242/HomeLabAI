# Home Lab AI: Project Status (Feb 12, 2026)

## Current Core Architecture: v3.5.x "Bicameral Dispatch"
*   **Orchestration**: Managed via **`lab-attendant.service` (systemd)**.
    *   **VRAM Guard**: Active. Pivoted to DCGM/Prometheus metrics for precise budget allocation.
    *   **Alpha Backend**: Toggleable vLLM support in Brain Node.
*   **The Communication Hub (Corpus Callosum)**:
    *   **Reflex Loop**: Characterful tics and thermal alerts verified non-blocking.
    *   **Strategic Sentinel**: Active. Brain listening for silicon-level logic.
    *   **Banter System**: Weighted TTL decay active.

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | Version 570.211.01 (CUDA 12.8) |
| **Archive Node** | ✅ STABLE | `patch_file` (Unified Diff) tool implemented. |
| **Pinky/Brain Nodes**| ✅ STABLE | Bicameral awareness prompts active. |
| **EarNode (STT)** | ✅ STABLE | Sledgehammer graph-disabling verified stable. |
| **VRAM Guard**   | ✅ STABLE | DCGM metrics and Stub fallback verified. |
| **Web Console** | ✅ STABLE | Workspace Auto-Save and multi-panel routing active. |

## Active Sprint: "The Nightly Recruiter" (v3.6)
*   **Tasks**:
    1.  [TODO] **Job Search Engine**: Implement scheduled "Alarm Clock" task to search for jobs and match against archive history. *Reasoning: High-value proactive agent application.*
    2.  [TODO] **Sleeping Weights**: Implement vLLM resident weight-sharing (Shared Model). *Reasoning: Minimize load-lurch and enable instant Hub response.*
    3.  [TODO] **Sentinel v2.0**: Implement "Strategic Uncertainty" interjection logic. *Reasoning: Move beyond keywords to logical pattern matching.*

## Recent Blockers Resolved
*   **VRAM Thrash**: Solved via Attendant-level engine selection (Ollama/vLLM/Stub).
*   **Chopstick Coding**: Solved via Strategic Patching (`patch_file`).
*   **Hub Latency**: Solved via Asynchronous Dispatch Hub.
