# Sprint Plan: SPR-11-07 "The Unity Restoration"
**Status:** DRAFT | **Version:** 1.0
**Context**: Following the vLLM 0.16.0 binary breakthrough (breaking the 333MiB wall).

## 🎯 Objective
To fully integrate **vLLM 0.16.0** as the primary inference engine for Linux residents, implementing the **Unity Pattern** via Multi-LoRA to minimize VRAM footprint and enable instantaneous node switching.

---

## 🏛️ Classification Matrix

### 1. Features (FEAT)
*   **[FEAT-030] Unity Pattern (Multi-LoRA Residency)**:
    *   **Status**: RESURRECTED (formerly Tabled).
    *   **Logic**: Run all concurrent resident nodes (Pinky, Brain, Architect, Archive) on a shared **Unified Base Model** (Llama-3.2-3B) footprint.
    *   **SCAR #5: Windows Isolation**: Windows (Node 'Brain') does NOT need to sync with Linux models. Attempting to force identical weight sets across the bridge is a performance trap.
*   **[FEAT-145] "Unity" Dispatcher (Hub Logic)**:
    *   **Logic**: Refactor `loader.py` and `acme_lab.py` to append `?lora=X` or include adapter names in the OpenAI payload when `lab_mode == "vLLM"`.

### 2. Vibe (VIBE)
*   **[VIBE-012] Hemispheric Independence**:
    *   **Behavior**: The Agent acknowledges the split between "High-Efficiency Residency" (Linux) and "Unconstrained Strategic Depth" (Windows). No model-matching is attempted across the bridge.

### 3. Lab Infrastructure (LAB)
*   **[LAB-004] vLLM Multi-LoRA Manifest**:
    *   **Silicon Note**: Local paths on `/speedy/models/adapters/` for `brain_v1`, `pinky_v1`, etc.
    *   **Environment**: Breakthrough flags (`XFORMERS`, `NCCL_P2P_DISABLE=1`) baked into the `lab-attendant.service`.

### 4. Operational Protocols (BKM)
*   **[BKM-021] The "Wall" Audit**:
    *   **Behavior**: Mandatory verification of the **333MiB Breakthrough** using `POST /ping` before committing architectural updates to production.

---

## 🏃 Execution Phases

### Phase 1: Hub & Loader Refactor
1.  Implement `FEAT-145` in `HomeLabAI/src/loader.py` to support adapter addressing.
2.  Update `acme_lab.py` to correctly route requests based on node identity.

### Phase 2: Production Hardening
1.  Update `lab-attendant.service` with breakthrough environment variables.
2.  Update `vram_characterization.json` to register vLLM as Tier 1.

### Phase 3: Validation (The works)
1.  Run **[BKM-021] Wall Audit**.
2.  Perform **[SMOKE]** test across 4 nodes.
3.  Verify **[VIBE-012]** by requesting a 70B response on Windows while Linux is unified on 3B.

---

## 🧪 Proof of Success
*   VRAM usage < 10GB with all 4 nodes + EarNode resident.
*   `POST /ping` returns coherent tokens.
*   Intercom log shows sub-second switching between "Pinky" and "Brain" source tags.
