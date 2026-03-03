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

#### 🍼 Baby Step 1: Residency & Inference Verified (Llama-1B)
*   **Goal**: Prove the stock v0.16.0 binary can pass the "333MiB Wall" and generate text.
*   **The Special Sauce**: `NCCL_SOCKET_IFNAME=lo` was the final missing piece, stabilizing the internal ZMQ handshakes.
*   **The Breakthrough Command**:
    ```bash
    NCCL_SOCKET_IFNAME=lo NCCL_P2P_DISABLE=1 VLLM_ATTENTION_BACKEND=XFORMERS \
    nohup ./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
        --model /speedy/models/Llama-3.2-1B-Instruct \
        --dtype float16 \
        --enforce-eager \
        --gpu-memory-utilization 0.5 \
        --max-model-len 4096 \
        --port 8088 > manual_vllm_step1.log 2>&1 &
    ```
*   **Result**: ✅ **SUCCESS**. VRAM reached 6.5GB. Coherent text ("*Pong*") verified via port 8088.

#### 🍼 Baby Step 2: Architecture Scar (Qwen-3B)
*   **Goal**: Upgrade to the "Unity" target (3B model).
*   **The Command**:
    ```bash
    NCCL_SOCKET_IFNAME=lo NCCL_P2P_DISABLE=1 VLLM_ATTENTION_BACKEND=XFORMERS \
    nohup ./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
        --model /speedy/models/Qwen2.5-3B-Instruct \
        --dtype float16 \
        --enforce-eager \
        --gpu-memory-utilization 0.5 \
        --max-model-len 4096 \
        --port 8088 > manual_vllm_step2.log 2>&1 &
    ```
*   **Result**: ❌ **FAILURE**. EngineCore failed with `KeyError: 'layers.0.mlp.gate_up_proj.weight'`.
*   **SCAR: Architecture Sensitivity**: vLLM 0.16.0's V1 engine is aggressive about weight-key naming. Qwen2.5 weights in `/speedy/models` lack the gate/up projection mapping expected by the v0.16.0 `Qwen2ForCausalLM` loader.

#### 🍼 Baby Step 4: SML Restoration & Phi-3.5-AWQ (The Fidelity Ladder)
*   **Goal**: Restore the "Small/Medium/Large" tiering using Turing-optimized models.
*   **Model Selection**: Standardized on **AWQ** for 3B+ models to ensure KV cache headroom.
*   **SNAG: Zombie VRAM Pressure**: Encountered a state where `nvidia-smi` reported 333MiB, but vLLM detected only 2.86GB free. This was caused by "Ghost" multiprocessing or ZMQ buffer residues from previous failed ignitions.
    *   **FIX**: A total **Silicon Purge** (`sudo fuser -kv /dev/nvidia0`) is mandatory if switching model architectures (e.g., Llama -> Phi).
*   **SNAG: FP16 Weight Pressure**: Verified that **Phi-3.5-mini (FP16)** is incompatible with 11GB vLLM v1. Its ~8GB weight footprint leaves < 1GB for KV cache after engine overhead.
    *   **FIX**: Pull and use **AWQ** versions for all models > 1B parameters.
*   **Result**: ✅ **SUCCESS**. Verified a three-tier Fidelity Ladder:
    *   **LARGE**: Llama-3.2-3B-AWQ (Verified ~6.5GB)
    *   **MEDIUM**: Phi-3.5-mini-AWQ (Verified ~5.5GB)
    *   **SMALL**: Llama-3.2-1B-FP16 (Verified ~4.5GB)

*   **SCAR: The WebSocket Hang (Mar 3, 2026)**: Attempting to `await ws.recv()` inside a synchronous shell command without a global timeout blocks the Agent turn. If the model chooses a tool instead of a direct response, the script hangs forever, triggering the CLI watchdog.
*   **STRATEGY: The Loopback Moat (127.0.0.1 vs 0.0.0.0)**:
    *   **Dev/Transitory**: Bind to `127.0.0.1` to ensure internal stability and zero external exposure during refactors. This aligns with the `lo` breakthrough (LAB-002) by preventing physical IP handshake traps.
    *   **Production**: Bind to `0.0.0.0` for appliance-grade reachability across the Bicameral network (Linux <-> Windows), secured via Cloudflare/Zero-Trust.
*   **Mandate**: Use "Trigger-Poll-Observe" pattern via Attendant registers and Trace Delta Capture.
*   **SCAR: The Physical IP Trap**: Without `NCCL_SOCKET_IFNAME=lo`, vLLM attempts handshakes on the physical NIC (192.168.x.x). On the Z87 board, this overhead causes a race condition that results in the process silently exiting during the ZMQ/NCCL initialization phase.
*   **SCAR: The HF Shadow-Lookup**: All local model paths **must be absolute** (starting with `/`). If a relative path is used, vLLM 0.16.0 defaults to a HuggingFace repository lookup and triggers an `OSError` crash.
*   **SCAR: The Watchdog Reaper**: The vLLM v1 core requires a ~45s warmup. If the parent CLI tool terminates before this completes, the background engine is often reaped unless decoupled via `nohup` or `systemd`.

### LAB-005: Modular Hub Architecture (v4.8 Refactor)
**Objective**: Decouple the monolithic `acme_lab.py` into specialized managers to improve maintainability and residency efficiency.

1.  **Sensory Layer (`SensoryManager`)**:
    *   **Role**: Handles binary audio buffers, VAD (Voice Activity Detection), and EarNode (NeMo) residency.
    *   **Invariant**: EarNode must be loaded **before** any cognitive nodes to claim contiguous VRAM.
2.  **Cognitive Layer (`CognitiveHub`)**:
    *   **Role**: Encapsulates reasoning logic, tool extraction, and node dispatching.
    *   **Feature**: Employs robust regex-based JSON extraction to handle banter-wrapped tool calls.
3.  **Observability Layer (Montana Protocol)**:
    *   **Role**: Centralized in `src/infra/montana.py`.
    *   **Function**: Reclaims log visibility from third-party libraries and injects the 4-part fingerprint `[BOOT_HASH : COMMIT : ROLE : PID]` into all streams.

4.  **Validation Checkpoints**:
    *   **The Wall**: Pass 333MiB VRAM usage within 20s.
    *   **Residency**: Pass 6000MiB+ VRAM allocation.
    *   **Warmup**: FlashInfer attention warmup must complete (approx 45s).
    *   **Inference**: Verify with "Narf! Ping" completion.

### LAB-003: The Unity Pattern (Multi-LoRA Residency)
**Objective**: Optimize multi-agent residency on the 11GB Turing budget.

> [!IMPORTANT]
> **Unity vs. SML**: The Unity Pattern (Single Active Foundation) should NOT be conflated with the **SML (Small/Medium/Large) Fallback** logic. 
> 1. **Unity** ensures that at any given moment, all active nodes share the *current* resident foundation to save VRAM. 
> 2. **SML** provides the resilience ladder to *switch* the entire foundation (the Unity base) to a different tier (e.g., 3B to 1B) during mode transitions (e.g., Text-Only to Voice Gateway).

1.  **Architecture**: The full Bicameral Mind (Pinky, Brain, Architect, Archive) should target a shared VRAM footprint using a **Unified Base Model** (e.g., Llama-3.2-3B) via vLLM 0.16.0.
2.  **Fast-Switching**: Leverage `--enable-lora` to swap node personas (Brain_v1, Pinky_v1) without reloading base weights.
3.  **SCAR: Windows Model Isolation**: Windows (Node 'Brain') does NOT need to sync with Linux models. Attempting to force identical weight sets across the bridge is a performance trap. Windows should leverage the RTX 4090's capacity for Mixtral/Llama-70B independently of the Linux resident tiering.

### LAB-004: vLLM Multi-LoRA Manifest
**Objective**: Hardcode model and adapter paths for consistent Turing residency.

1.  **Verified Foundation Paths**:
    *   **LARGE/MEDIUM**: `/speedy/models/llama-3.2-3b-instruct-awq`
    *   **SMALL**: `/speedy/models/Llama-3.2-1B-Instruct`
2.  **Adapter Path**: `/speedy/models/adapters/`.
    *   `brain_v1`: Strategic strategic adapter.
    *   `pinky_v1`: Intuitive gateway adapter.
3.  **Registration**: All models must be registered in `infrastructure.json` with absolute paths to prevent "Weight Volatility."
