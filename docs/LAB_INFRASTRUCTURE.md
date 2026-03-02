# 🏗️ Lab Infrastructure: Physical & Logic Anchors [v1.0]
**"The Grounding Wire"**

## 📍 Physical Storage & Mounts
| Mount Point | Label | Capacity | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | `rpool` | ~40GB | System OS, Configs, Logs. **High Pressure.** |
| `/home` | `rpool` | ~600GB | User data, Venvs. **High Pressure.** |
| `/speedy` | `speedy` | 150GB | **High-Speed Btrfs SSD.** Primary home for LLM weights. |
| `/mnt/2TB` | `2TB` | 2TB | Bulk storage (Ext4). |
| `/media/jallred/jellyfin` | `jellyfin` | 4TB | Media & Cold Archive (Ext4). |

## 🛠️ Tool Availability
*   **Migration**: `rsync`, `rclone` (configured for GDrive).
*   **Monitoring**: `nvidia-smi` (v550+), `df -h`, `lsblk`, `NVIDIA DCGM` (Continuous Telemetry).
*   **Automation**: `systemd` (`lab-attendant.service`).

## ⚙️ Hardware Characteristics
*   **Host**: `z87-Linux` (Native).
*   **GPU**: NVIDIA RTX 2080 Ti (11GB VRAM).
    *   **Architecture**: Turing (`sm_75`).
    *   **Constraint**: No native `bfloat16` support for fused kernels (use `float16` for Liger).
*   **Network**: Tailscale MagicDNS active.

## 🔗 Critical Symlinks
*   `~/Dev_Lab/models/hf_downloads` -> `/speedy/models` (In progress).

---

## 🚀 Infrastructure Playbooks

### LAB-001: Silicon Bringup (Hardware & Service Restoration)
**Objective**: Restore the Lab environment from a powered-off or crashed state.

1.  **Hardware/Driver Audit**:
    *   Execute `nvidia-smi`.
    *   **Success**: Driver version (e.g., 550+) and CUDA (e.g., 12.4+) reported.
    *   **Failure**: If "could not communicate with driver," perform kernel/driver maintenance and reboot.

2.  **The Invariant Sensory Core (EarNode)**:
    *   **Action**: Verify `EarNode` (NeMo) is responsive before starting cognitive engines.
    *   **Logic**: Sensing is the invariant constant of the Lab; reasoning is secondary.

3.  **Orchestrator Liveliness (`lab-attendant`)**:
    *   Execute `sudo systemctl status lab-attendant.service`.
    *   **Action**: If stopped, `sudo systemctl restart lab-attendant.service`.
    *   **Verification**: `curl http://localhost:9999/heartbeat` should return JSON.

4.  **Lab Server Ignition**:
    *   **Action**: `curl -X POST http://localhost:9999/start -H "Content-Type: application/json" -d '{"mode": "SERVICE_UNATTENDED", "disable_ear": true}'`
    *   **Verification**: `tail -f HomeLabAI/server.log` (Watch for `[READY] Lab is Open`).

5.  **Uplink Verification**:
    *   `tail -f HomeLabAI/server.log` 
    *   Handshake via `intercom.py`.
