# Home Lab AI: Project Status (Feb 11, 2026)

## Current Core Architecture: v3.4.x "Integrated Workbench"
*   **Orchestration**: Transitioned from manual `nohup` to **`lab-attendant.service` (systemd)**.
    *   Attendant manages `acme_lab.py` lifecycle via HTTP API (`9999`).
    *   Automated log archiving and `stderr` redirection.
*   **Inference Server (`acme_lab.py`)**:
    *   **Stable Baseline**: Sequential resident initialization verified.
    *   **Logging**: Montana Protocol active (stderr authority).
    *   **Lobby**: Multi-stage INIT reporting (Archive Ready -> Pinky Ready -> etc).

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | Version 570.211.01 (CUDA 12.8) |
| **Archive Node** | ✅ STABLE | Sequential init verified. |
| **Pinky/Brain Nodes**| ✅ STABLE | MCP handshakes functional. |
| **EarNode (STT)** | ⚠️ CRASHING | `list index out of range` during `from_pretrained`. |
| **Web Console** | ✅ STABLE | Handshake v3.4.0 verified. |

## Active Sprint: EarNode Stability (NeMo v2.6.1)
*   **The Problem**: NeMo fails during model load on CUDA 12.8.
*   **The Plan**: 
    1.  Verify `EAR_NODE_STUB_MODEL=1` passes through Attendant.
    2.  Identify why `torch.backends.cudnn.enabled = False` isn't bypassing the `from_pretrained` crash.
    3.  Evaluate NeMo v2.6.1 compatibility with the new 570 driver stack.

## Recent Blockers Resolved
*   **NVIDIA Driver Catastrophe**: Solved via purge/reinstall and initramfs update.
*   **Logger Hijacking**: Solved via Montana Protocol.
*   **Process Ghosting**: Solved via Lab Attendant Service.
