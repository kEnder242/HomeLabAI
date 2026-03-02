# Sprint Plan: vLLM 0.16.0 Silicon Gauntlet
**Status:** ACTIVE | **Version:** 1.0
**Target Hardware:** NVIDIA RTX 2080 Ti (Turing / Compute 7.5 / 11GB VRAM)

## 🎯 Objective
To evaluate **vLLM v0.16.0** for stable multi-LoRA residency on Turing hardware, specifically aiming to break the **"333MiB Wall"** that plagued previous versions.

## 🏺 Historical Context & Scars
*   **The 333MiB Wall**: Diagnosed in **[STABILIZATION_REPORT_FEB_13.md](../STABILIZATION_REPORT_FEB_13.md)**. Previous vLLM versions (0.5.0 - 0.15.1) hit a silent deadlock during the Ray/NCCL handshake when mapping BF16 tensors to Turing's lack of native BF16 units.
*   **Aggressive Healing**: Documented in **[ATTENDANT_PROTOCOL.md](../ATTENDANT_PROTOCOL.md)**. The Lab Attendant historically killed experimental processes because it misinterpreted manual downtime as a system crash, re-allocating VRAM and causing collisions.
*   **The Unity Pattern**: A forced pivot to **Ollama** (documented in **[RETROSPECTIVE_VLLM_RESURRECTION.md](../../../Portfolio_Dev/RETROSPECTIVE_VLLM_RESURRECTION.md)**) to handle BF16->FP16 casting safely.

## 🛠️ Strategy: The "Experimental Pilot"
We will leverage existing infrastructure formulas while adding a new "Maintenance Silence" layer.

### 1. Leveraged Formulas
*   **[FEAT-119] The Assassin**: Uses `fuser -k` and PGID termination to clear the deck before tests.
*   **[FEAT-021] Dynamic Venv**: Uses the Attendant's ability to override the Python binary path for the experimental sandbox.

### 2. New Logic: Maintenance Silence
To prevent "Aggressive Healing" during driver/engine tests, the Attendant will now respect the `maintenance.lock`.

```python
# Proposed logic for lab_attendant.py
if os.path.exists(MAINTENANCE_LOCK):
    logger.info("[WATCHDOG] Maintenance Lock active. Passive mode engaged.")
    return # Skip recovery/restarting
```

## 🏃 Execution Steps

### Phase A: Quiesce & Lock
1.  Send `POST /stop` to the Attendant (Port 9999) to clear production residents.
2.  `touch Portfolio_Dev/field_notes/data/maintenance.lock` to freeze the orchestrator.

### Phase B: The Forensic Launch
Launch vLLM 0.16.0 from the `~/.venv_vllm_016` sandbox using the FP8 Llama model to maximize Turing compatibility.

**Launcher Command Idea:**
```bash
export VLLM_ATTENTION_BACKEND=XFORMERS  # Bypasses FlashInfer BF16 risks
./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server 
    --model /speedy/models/Llama-3.2-3B-Instruct-FP8 
    --dtype float16 
    --enforce-eager 
    --gpu-memory-utilization 0.7 
    --port 8088
```

### Phase C: Forensic Monitoring
Use a new script `src/debug/monitor_wall.py` to watch for the 333MiB "deadlock signature."

```python
# monitor_wall.py Snippet
if vram > 350:
    print("[SUCCESS] 333MiB Wall Broken. Proceeding to inference test.")
```

## 🧪 Verification & Proof
*   **Primary Proof**: VRAM usage reaches ~7GB (0.7 utilization) without a deadlock.
*   **Inference Proof**: `src/debug/repro_vllm_400.py` returns a valid "Poit!" from the 8088 port.
*   **Stability Proof**: **[stability_marathon_v2.py](../debug/stability_marathon_v2.py)** passes a 300s stress test.

## 🔗 Internal Links
*   **Venv**: `/home/jallred/Dev_Lab/.venv_vllm_016`
*   **Models**: `/speedy/models/` (Qwen2.5, Llama-3.2-FP8)
*   **Attendant**: `HomeLabAI/src/lab_attendant.py`
