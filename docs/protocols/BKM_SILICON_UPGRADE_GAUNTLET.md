# BKM: Silicon Upgrade Gauntlet [v1.2]
**Role:** [BKM] - Safety Protocol for Host/Driver/Engine Transitions
**Objective:** To migrate Z87-Linux to NVIDIA 565+ drivers, latest kernel, and vLLM 0.17 without inducing initialization deadlocks or VRAM fragmentation.

---

## 🛑 0. Operational State Control (The SSH Gate)
Before touching drivers, you MUST release all hardware handles:
1.  **Stop the Lab**: `sudo systemctl stop lab-attendant` (Prevents zombie GPU processes).
2.  **Stop the GUI**: `sudo systemctl stop gdm` or `lightdm` (Releases X11/Wayland driver locks).
3.  **Persistence**: Execute all following steps inside **Zellij** or **Tmux**. If the SSH session blips during `initramfs` generation, the background process must survive.

## 🏎️ 1. Preparation (One-Liner Baseline)
... (baseline commands) ...

## 🛠️ 2. Core Execution Logic (The "Why")

### Phase A: The Host Layer (Kernel & Drivers)
*   **The Command**: `sudo apt-get purge nvidia-* && sudo apt-get autoremove && sudo apt-get install nvidia-driver-565`
*   **Availability Note**: As of March 2026, `565` is the primary available branch in the repos. `560` may require `ppa:graphics-drivers/ppa`.
*   **Critical Step**: `sudo update-initramfs -u` after installation to force the new driver into the boot stage.
*   **The Sync (Reboot)**: `sudo reboot` now. You cannot verify drivers or DKMS modules without a fresh kernel load.

### Phase B: The Engine Layer (vLLM 0.17)
... (vLLM logic) ...
*   **The Command**: `pip install vllm==0.17.0 --extra-index-url https://download.pytorch.org/whl/cu121`
*   **Library Conflict Gate**: vLLM 0.17 bundles its own CUDA libraries. To prevent `CUBLAS_STATUS_INVALID_VALUE` errors when system drivers are 565+, you must:
    *   `unset LD_LIBRARY_PATH` before launching.
    *   Set `VLLM_ENABLE_CUDA_COMPATIBILITY=0`.
*   **The Why**: vLLM 0.17 introduces refined `BlockManager` logic. We must verify that the `--gpu-memory-utilization 0.5` floor still provides the required ~1.5GB headroom for the EarNode.
*   **The Constraint**: Maintain `--enforce-eager` unless 0.17 explicitly resolves the Turing CUDA Graph "unpacking" mismatch.

## ⛩️ 3. Specific Trigger Points (The "Gate")
The upgrade is only considered **VERIFIED** if these three gates are cleared in sequence:

1.  **The Sentry Gate**: `nvidia-smi` returns without delay and shows 0MiB utilization on a fresh boot.
2.  **The Wall Audit**: `python3 HomeLabAI/src/debug/test_vram_guard.py` clears the "333MiB Wall" during vLLM initialization.
3.  **The Heartbeat**: `curl -X POST http://localhost:8088/v1/chat/completions` (Direct vLLM) returns a valid token stream within <2000ms.

## 🤕 4. Scars & Preventive Retrospective
*   **Scar #1 (Feb 11)**: Kernel update killed driver communication. 
    *   *Prevention*: Verify `dkms status` shows the driver as "installed" for the active kernel before rebooting.
*   **Scar #2 (Feb 15)**: Ray/NCCL deadlocks on loopback. 
    *   *Prevention*: vLLM 0.17 requires `VLLM_CONFIGURE_LOGGING=0` to prevent logger hijacking from killing the startup sequence (The Montana Protocol).
*   **Scar #3 (Feb 20)**: VRAM fragmentation from NeMo.
    *   *Prevention*: Load vLLM *before* the EarNode. 0.17's aggressive cache allocation may prevent NeMo from claiming its resident 1.5GB if the order is reversed.

---
## 📜 Execution Log (Audit Trail)
*   **2026-03-10 13:55**: [GATE 0] REBOOT SUCCESS. Active Kernel: `6.14.0-36-generic`. Drivers: `PURGED`.
*   **2026-03-10 14:15**: [NETWORK] Restored Wi-Fi via `linux-modules-extra`. Speed verified at 123Mbit/s.
*   **2026-03-10 14:27**: [PHASE A] Driver 580 installed. `nvidia-smi` verified.
*   **2026-03-10 14:50**: [PHASE B] vLLM 0.17 environment `.venv_vllm_017` created.
*   **2026-03-10 15:20**: [GATE 3] Heartbeat SUCCESS. Qwen-2.5-1.5B responding on port 8088.
*   **2026-03-13 14:45**: [SPR-13.0] **PRODUCTION WIN**. Successfully baseline-stabilized **Llama-3.2-3B-AWQ** on vLLM 0.17 using the **TRITON_ATTN** backend and **0.5 utilization** config. Environment consolidated into `HomeLabAI/.venv`.
*   **STATUS**: **VERIFIED PRODUCTION READY**.

---

## [SPR-13.0] Finalized vLLM 0.17 "Win Recipe" (Mar 13, 2026)
**Context:** Standardizing the **Unified 3B Base** on the RTX 2080 Ti (11GB). Resolves the FlashInfer JIT build failures encountered on Compute 7.5 silicon.

### 🏛️ The Configuration
*   **Model:** `llama-3.2-3b-instruct-awq` (UNIFIED Tier).
*   **Backend:** `TRITON_ATTN` (Mandatory; bypasses failing FlashInfer JIT).
*   **Utilization:** `0.5` (The "Safe Win"; provides necessary KV cache block allocation).
*   **Engine Mode:** vLLM V1 (Native in 0.17; `VLLM_USE_V1=0` is ignored by the engine).
*   **Network:** `NCCL_P2P_DISABLE=1` and `NCCL_SOCKET_IFNAME=lo` (Bypasses the 333MiB stall).

### 🩺 Verification Gate
*   **Audit Tool:** `python3 HomeLabAI/src/debug/test_vram_guard.py`
*   **Success Logic:** Physical VRAM Breakthrough (>400MiB) + Inference Ping (HTTP 200).
*   **VRAM Peak (Static):** 5125 MiB (verified).

--
**"Trust the silicon, then the soul."**
