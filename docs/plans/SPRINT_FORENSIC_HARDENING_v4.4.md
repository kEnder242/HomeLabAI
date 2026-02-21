# Sprint Plan: Forensic Hardening v4.4
**Status:** ACTIVE
**Objective:** Resolve discrepancies identified in the Feb 20 audit and harden the Lab's verification suite.

## 📋 Task List

### 0. [FEAT-080] Dynamic Model Fluidity
- [x] **[DONE]** Implement `get_best_model()` in `loader.py` to dynamically query host tags.
- [x] **[DONE]** Harmonize `acme_lab.py` health-check model prioritization.
- [x] **[DONE]** Harden Forensic Mirroring with absolute pathing.
- [x] **[DONE]** Perform final code hygiene sweep (dots/versioning).

### 1. Orchestrator Hygiene (`acme_lab.py`)
- [x] **[DONE]** Remove any literal `...` placeholders or indentation artifacts from `execute_dispatch`.
- [ ] **[TODO]** Move `internal_debate` and `recruiter` imports to top-level or protected import blocks.
- [ ] **[TODO]** Verify and fix `self.banter_backoff` initialization in `__init__`.

### 2. Version Synchronization
- [x] **[DONE]** Synchronize all version strings to **v3.8.0**:
    - `acme_lab.py` (Server)
    - `intercom_v2.js` (Web Client)
- [ ] **[TODO]** Synchronize `test_pi_flow.py` (Verification script)

### 3. Ledger Alignment (`DIAGNOSTIC_RUNDOWN.md`)
- [ ] **[TODO]** Map newly created tests to the Physician's Ledger:
    - `src/debug/test_mib_wipe.py`
    - `src/debug/test_banter_decay.py`
    - `src/debug/test_strategic_sentinel.py`
- [ ] **[TODO]** Perform final bit-perfect audit of all listed paths.

### 4. Extended Forensic Rescue
- [ ] **[TODO]** Review the remaining 19 deleted files from Feb 19 for viability.
- [ ] **[TODO]** Restore `test_aiohttp.py` and `gate_triage_audit.py` if they align with the current architecture.
- [ ] **[TODO]** Fix any broken imports in restored scripts.

### 5. UI Routing & Labeling Hardening
- [ ] **[TODO]** Update `intercom_v2.js` to ensure `source: System` messages with strategic intent route to the Insight panel.
- [ ] **[TODO]** Harden `Reflex` labeling to prevent routing confusion.

### 6. Git State Verification
- [ ] **[TODO]** Explicitly `git add` the entire `src/debug/` folder to ensure no rescued files are untracked.
- [ ] **[TODO]** Perform final status check.

### 7. Validation Sweep
- [ ] **[TODO]** Run the "Diamond Suite" (non-looping tests).
- [ ] **[TODO]** Identify and skip long-running/looping tests (e.g., `stability_marathon`).

---
**Baseline Commit:** [PENDING]
**Completion Commit:** [PENDING]
