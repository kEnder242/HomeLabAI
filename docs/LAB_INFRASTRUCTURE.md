# Lab Infrastructure: The Physical Floor
**Role: [LAB] - Silicon Laws & Environment Anchors**

> [!IMPORTANT]
> **PURPOSE:** This is the technical ledger for the physical environment.
> **[LAB]**: Hardware specs, mount points, absolute local paths, and environment-specific playbooks (e.g., Turing-specific breakthroughs).

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

### LAB-002: vLLM 0.16.0 Breakthrough Recipe (Turing/RTX 2080 Ti)
**Objective**: Maintain high-fidelity vLLM residency on 11GB Turing hardware without Ray/NCCL deadlocks.

1.  **The "Magic Combination" (Environment Flags)**:
    *   `VLLM_ATTENTION_BACKEND=XFORMERS`: Bypasses FlashInfer/FA2 kernels that frequently contain BF16 instructions fatal to Turing.
    *   `NCCL_P2P_DISABLE=1`: Essential for Z87/Single-GPU systems to prevent peer-to-peer handshake hangs during KV cache profiling.

2.  **Orchestration Command**:
    ```bash
    ./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
        --model /speedy/models/Llama-3.2-1B-Instruct \
        --dtype float16 \
        --enforce-eager \
        --gpu-memory-utilization 0.5 \
        --max-model-len 4096 \
        --enable-lora \
        --port 8088
    ```

3.  **Validation Checkpoints**:
    *   **The Wall**: Pass 333MiB VRAM usage within 20s.
    *   **Warmup**: FlashInfer attention warmup must complete (approx 45s).
    *   **Inference**: Verify with "Narf! Ping" completion.

### LAB-003: The Unity Pattern (Multi-LoRA Residency)
**Objective**: Optimize multi-agent residency on the 11GB Turing budget.

1.  **Architecture**: The full Bicameral Mind (Pinky, Brain, Architect, Archive) should target a shared VRAM footprint using a **Unified Base Model** (e.g., Llama-3.2-3B) via vLLM 0.16.0.
2.  **Fast-Switching**: Leverage `--enable-lora` to swap node personas (Brain_v1, Pinky_v1) without reloading base weights.
3.  **SCAR: Windows Model Isolation**: Windows (Node 'Brain') does NOT need to sync with Linux models. Attempting to force identical weight sets across the bridge is a performance trap. Windows should leverage the RTX 4090's capacity for Mixtral/Llama-70B independently of the Linux resident tiering.

### LAB-004: vLLM Multi-LoRA Manifest
**Objective**: Hardcode model and adapter paths for consistent Turing residency.

1.  **Base Model Path**: `/speedy/models/Qwen2.5-3B-Instruct` (or `Llama-3.2-1B-Instruct`).
2.  **Adapter Path**: `/speedy/models/adapters/`.
    *   `brain_v1`: Strategic strategic adapter.
    *   `pinky_v1`: Intuitive gateway adapter.
3.  **Registration**: All models must be registered in `infrastructure.json` with absolute paths to prevent "Weight Volatility."
