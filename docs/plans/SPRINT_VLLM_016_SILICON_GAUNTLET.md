# Sprint Plan: vLLM 0.16.0 Silicon Gauntlet
**Status:** ACTIVE | **Version:** 1.2
**Target Hardware:** NVIDIA RTX 2080 Ti (Turing / Compute 7.5 / 11GB VRAM)

## 🎯 Objective
To evaluate **vLLM v0.16.0** for stable residency on Turing hardware, specifically aiming to break the **"333MiB Wall"** and achieve a functional `[READY]` state using integrated Attendant orchestration.

## 🏺 Historical Context & Scars
*   **The 333MiB Wall**: Diagnosed in **[STABILIZATION_REPORT_FEB_13.md](../STABILIZATION_REPORT_FEB_13.md)**. Historically, vLLM hit a silent deadlock during Ray/NCCL handshakes due to BF16 hardware mismatches.
*   **The V1 Engine Lockdown**: Discovered during forensic code review (**[vLLM_016_REVIEW.md](../../../Portfolio_Dev/docs/vLLM_016_REVIEW.md)**). vLLM 0.16.0 has removed the legacy V0 path for the API server, forcing a multiprocessing V1 core using ZeroMQ (ZMQ).
*   **Aggressive Healing**: Documented in **[ATTENDANT_PROTOCOL.md](../ATTENDANT_PROTOCOL.md)**. The Lab Attendant historically killed experimental processes, causing VRAM collisions.

## 🛠️ Strategy: The Laboratory Pilot (v1.2 Integrated)
We will leverage existing infrastructure while adding a new "Maintenance Silence" layer directly into the Attendant API.

### 1. Attendant API Extensions (New Features)
Instead of manual shell commands, we will implement native "Experimental" controls in `lab_attendant.py`:
*   **[FEAT-142] `POST /quiesce`**: Sets `maintenance.lock`, stops active residents, and reaps all ports.
*   **[FEAT-143] `POST /ignition`**: Removes `maintenance.lock` and triggers immediate boot.
*   **[FEAT-144] `POST /ping`**: Integrated health verification via the Attendant API.

### 2. Maintenance Silence
The Attendant now respects the `maintenance.lock`, ensuring the orchestrator remains passive during high-risk experiments.

---

## 🏃 Plan A: The Unified Binary Gauntlet
**Goal**: Reach `[READY]` using the stock v0.16.0 binary with environment-level Turing workarounds.

### 1. Rationale
Earlier breakthroughs tonight proved that **XFORMERS** and **NCCL_P2P_DISABLE=1** allow the binary to pass the 333MiB wall and reach 1200MiB+. Plan A focuses on stabilizing the subsequent V1 coordinator handshake.

### 2. Execution Command (Orchestrated)
```bash
curl -X POST http://localhost:9999/start \
    -H "Content-Type: application/json" \
    -d '{
        "engine": "VLLM",
        "venv_path": "/home/jallred/Dev_Lab/.venv_vllm_016",
        "extra_args": "--dtype float16 --enforce-eager --gpu-memory-utilization 0.7 --max-model-len 4096",
        "mode": "EXPERIMENTAL"
    }'
```

---

## 🏃 Plan B: The Targeted Source Build (Nuclear Option)
**Goal**: Compile v0.16.0 specifically for Compute 7.5 to strip incompatible kernels.

### 1. Rationale
Plan B uses a "Build-to-Target" strategy to ensure no illegal instructions or incompatible NCCL paths are even present in the binary. This is the fallback if Plan A binary fails the final profiling.

### 2. Setup & Constraints
*   **Location**: `/home/jallred/Dev_Lab/vllm_source` (rpool/ZFS).
*   **Compiler Flags**: `TORCH_CUDA_ARCH_LIST="7.5"`, `MAX_JOBS=4`.

---

## 🧪 Verification & Proof
*   **Primary Proof**: VRAM usage reaches ~7GB without a deadlock.
*   **Inference Proof**: `curl -X POST http://localhost:9999/ping` returns a valid "Narf! Ping" response.
*   **Stability Proof**: **[stability_marathon_v2.py](../debug/stability_marathon_v2.py)** passes a 300s stress test.

## 🔗 Internal Links
*   **Source Code**: `~/Dev_Lab/vllm_source` (Cloned Mar 2, 2026)
*   **Venv**: `~/.venv_vllm_016`
*   **Models**: `/speedy/models/` (Qwen2.5-3B-Instruct)
*   **Review**: **[vLLM_016_REVIEW.md](../../../Portfolio_Dev/docs/vLLM_016_REVIEW.md)**
