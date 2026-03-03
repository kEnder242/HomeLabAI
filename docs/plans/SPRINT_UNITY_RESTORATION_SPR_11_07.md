# Sprint Plan: SPR-11-07 "The Unity Restoration"
**Status:** ACTIVE | **Version:** 1.1
**Context**: Following the vLLM 0.16.0 binary breakthrough (breaking the 333MiB wall).

## 🎯 Objective
To fully integrate **vLLM 0.16.0** as the primary inference engine for Linux residents, implementing the **Unity Pattern** via Multi-LoRA to minimize VRAM footprint and enable instantaneous node switching.

---

## 🏛️ Classification Matrix

### 1. Features (FEAT)
*   **[FEAT-030] Unity Pattern (Multi-LoRA Residency)**:
    *   **Status**: ACTIVE.
    *   **Logic**: Run all concurrent resident nodes (Pinky, Brain, Architect, Archive) on a shared **Unified Base Model** (Llama-3.2-3B) footprint.
    *   **SCAR #5: Windows Isolation**: Windows (Node 'Brain') does NOT need to sync with Linux models. Attempting to force identical weight sets across the bridge is a performance trap.
*   **[FEAT-145] "Unity" Dispatcher (Hub Logic)**:
    *   **Logic**: Refactor `loader.py` and `acme_lab.py` to support Named LoRAs per resident.

### 2. Vibe (VIBE)
*   **[VIBE-012] Hemispheric Independence**:
    *   **Behavior**: High-fidelity strategic depth on Windows (unconstrained); high-efficiency residency on Linux (unified).

### 3. Lab Infrastructure (LAB)
*   **[LAB-004] vLLM Multi-LoRA Manifest**:
    *   **Silicon Note**: Hardcoded paths for `brain_v1`, `pinky_v1` on `/speedy/models/adapters/`.
    *   **Environment**: breakthrough flags (`XFORMERS`, `NCCL_P2P_DISABLE=1`) baked into the `lab-attendant.service`.

---

## 🏃 Execution Phases

### Phase 1: Hub & Loader Refactor
1.  Implement `FEAT-145` in `src/loader.py` to support `lora_request` addressing.
2.  Refactor `acme_lab.py` to assign node-specific LoRA names during dispatch.

### Phase 2: High-Fidelity Verification (The Gauntlet)
1.  **[APOLLO] VRAM Characterization**: Run `src/debug/test_apollo_vram.py` to verify the 0.16.0 active peak fits within 11GB.
2.  **[SMOKE] Inference Parity**: Run `src/vllm_smoke_test.py` to confirm coherent model responses from port 8088.
3.  **[DEEP SMOKE] Cycle of Life**: Execute `acme_lab.py --mode DEEP_SMOKE` to verify end-to-end integration (Ingest -> Reason -> Dream -> Recall).

### Phase 3: Production Ignition
1.  Update `vram_characterization.json` to register vLLM 0.16.0 as Tier 1 (Nominal).
2.  Trigger `POST /ignition` to bring the unified stack online.

---

## 🧪 Proof of Success
*   VRAM usage < 10.5GB with full resident stack + EarNode.
*   Deep Smoke cycle completes with verified memory recall.
*   Intercom log confirms sub-second switching between node personas.

---

## 📉 End of Session Report (Mar 2, 2026)

### 1. Modifications Summary
*   **Loader Refactor (`src/nodes/loader.py`)**: Implemented [FEAT-145] to support `lora_request` payloads. Added a defensive "Adaptive Unity" check that only requests a LoRA if the adapter directory exists, preventing vLLM V1 worker crashes.
*   **Attendant API Expansion (`src/lab_attendant.py`)**: 
    *   Implemented native `POST /quiesce` (Lockdown), `POST /ignition` (Reboot recovery), and `POST /ping` (Health probe).
    *   Hardened the vLLM ignition sequence with breakthrough flags: `VLLM_ATTENTION_BACKEND=XFORMERS` and `NCCL_P2P_DISABLE=1`.
    *   Resolved "Argument Bleed" by isolating vLLM CLI flags in environment variables.
*   **VRAM Grounding**: Promoted vLLM 0.16.0 to Tier 1 in `vram_characterization.json` with a 0.7 utilization target.

### 2. Current Trajectory
We are at the threshold of **Phase 2: High-Fidelity Verification**. The "Unity" infrastructure is physically present and patched. The breakthrough proved that vLLM 0.16.0 binary **can** run on Turing hardware if forced into the legacy V0 path via environment variables and specific backend selections.

### 3. Forensic Scars & Obstacles
*   **Dependency Entropy**: The new `~/.venv_vllm_016` required a second pass of `pip install` for Lab-critical libraries (`chromadb`, `sentence-transformers`, `pynvml`).
*   **V1 Core Sensitivity**: vLLM 0.16.0's new V1 engine is significantly more aggressive during initialization. It requires a quiet environment and stable networking (NCCL) to pass its internal profiling.
*   **Split-Brain Orchestration**: Encountered issues where stale Attendant processes survived service restarts, leading to confusing log entries and argument errors. Final resolution required a total silicon purge.

**Next Immediate Task**: Run the `DEEP_SMOKE` cycle to confirm archival integration.
