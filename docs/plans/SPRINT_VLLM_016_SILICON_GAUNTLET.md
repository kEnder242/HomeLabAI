# Sprint Plan: vLLM 0.16.0 Silicon Gauntlet
**Status:** ACTIVE | **Version:** 1.1
**Target Hardware:** NVIDIA RTX 2080 Ti (Turing / Compute 7.5 / 11GB VRAM)

## 🎯 Objective
To evaluate **vLLM v0.16.0** for stable residency on Turing hardware, specifically aiming to break the **"333MiB Wall"** and achieve a functional `[READY]` state.

## 🏺 Historical Context & Scars
*   **The 333MiB Wall**: Diagnosed in **[STABILIZATION_REPORT_FEB_13.md](../STABILIZATION_REPORT_FEB_13.md)**. Historically, vLLM hit a silent deadlock during Ray/NCCL handshakes due to BF16 hardware mismatches.
*   **The V1 Engine Lockdown**: Discovered during forensic code review (**[vLLM_016_REVIEW.md](../../../Portfolio_Dev/docs/vLLM_016_REVIEW.md)**). vLLM 0.16.0 has removed the legacy V0 path for the API server, forcing a multiprocessing V1 core using ZeroMQ (ZMQ).
*   **Aggressive Healing**: Documented in **[ATTENDANT_PROTOCOL.md](../ATTENDANT_PROTOCOL.md)**. The Lab Attendant historically killed experimental processes, causing VRAM collisions.

## 🛠️ Strategy: The Laboratory Pilot
We will leverage existing infrastructure while adding a new "Maintenance Silence" layer.

### 1. Leveraged Infrastructure
*   **[FEAT-119] The Assassin**: Uses `fuser -k` to clear the deck before tests.
*   **[FEAT-138] Maintenance Silence**: Patched `lab_attendant.py` to respect `maintenance.lock`, ensuring the orchestrator remains passive during high-risk experiments.

---

## 🏃 Plan A: The Unified Binary Gauntlet
**Goal**: Reach `[READY]` using the stock v0.16.0 binary with environment-level Turing workarounds.

### 1. Rationale
Earlier breakthroughs tonight proved that **XFORMERS** and **NCCL_P2P_DISABLE=1** allow the binary to pass the 333MiB wall and reach 1200MiB+. Plan A focuses on stabilizing the subsequent V1 coordinator handshake.

### 2. Execution Command
```bash
export VLLM_ATTENTION_BACKEND=XFORMERS  # Bypasses FlashInfer BF16 risks
export NCCL_P2P_DISABLE=1               # Prevents single-GPU Z87 deadlocks
./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model /speedy/models/Qwen2.5-3B-Instruct \
    --dtype float16 \
    --enforce-eager \
    --gpu-memory-utilization 0.7 \
    --max-model-len 4096 \
    --port 8088
```

### 3. Monitoring
Use **`src/debug/monitor_wall.py`** to watch for the 333MiB breakthrough.

---

## 🏃 Plan B: The Targeted Source Build (Nuclear Option)
**Goal**: Compile v0.16.0 specifically for Compute 7.5 to strip incompatible kernels.

### 1. Rationale
The code review confirmed that vLLM v1 architecture heavily prioritizes Flash Attention 2 (Compute 8.0+). Plan B uses a "Build-to-Target" strategy to ensure no illegal instructions or incompatible NCCL paths are even present in the binary.

### 2. Setup & Constraints
*   **Location**: `/home/jallred/Dev_Lab/vllm_source` (rpool/ZFS chosen for robustness and 244GB available space).
*   **Environment**: Dedicated `~/.venv_vllm_build`.
*   **Compiler Flags**:
    *   `export TORCH_CUDA_ARCH_LIST="7.5"`: Forces Turing-only binary generation.
    *   `export MAX_JOBS=4`: Prevents 32GB system RAM exhaustion during C++ linking.
*   **Deployment**: Final `.so` artifacts will be symlinked to `/speedy` for model-loading performance.

---

## 🧪 Verification & Proof
*   **Primary Proof**: VRAM usage reaches ~7GB without a deadlock.
*   **Inference Proof**: `src/debug/repro_vllm_400.py` returns a valid "Poit!" from port 8088.
*   **Stability Proof**: **[stability_marathon_v2.py](../debug/stability_marathon_v2.py)** passes a 300s stress test.

## 🔗 Internal Links
*   **Source Code**: `~/Dev_Lab/vllm_source` (Cloned Mar 2, 2026)
*   **Venv**: `~/.venv_vllm_016`
*   **Models**: `/speedy/models/` (Qwen2.5-3B-Instruct)
*   **Review**: **[vLLM_016_REVIEW.md](../../../Portfolio_Dev/docs/vLLM_016_REVIEW.md)**
