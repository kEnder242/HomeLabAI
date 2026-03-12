# Sprint Plan: [SPR-5.0] The Great Consolidation
**Version:** 5.0 (Phase 12 Architectural Hardening)
**Goal:** Unify the Lab into a single, modern virtual environment, eliminating the "Split-Brain" complexity and the risk of dependency drift.

## 🎯 The Mission
To surgically merge all required dependencies into a single `.venv` (`HomeLabAI/.venv`), decommission all legacy virtual environments, and harden the systemd service to prevent future fragmentation.

---

## 🧬 Architectural Anchors (The "Why")

### 1. The Dependency Collision (Root Cause)
The Lab's stability was compromised by a version mismatch between two environments:
*   `.venv_vllm_017`: Built for performance (pydantic v2, torch 2.x).
*   `.venv_legacy`: Built for stability with older tools (pydantic v1).

### 2. The "DNA-First" Merge (The Solution)
Instead of brute-forcing conflicting requirements, we are using `pip`'s dependency resolver to our advantage. By starting with the modern environment and surgically injecting only the *core* legacy packages (`chromadb`, `nemo-toolkit`, `playwright`), `pip` will automatically fetch the latest *compatible* sub-dependencies, resolving the conflicts for us.

---

## 🛠️ Implementation Tasks & Verification

### Phase 1: Dependency Merge (Agentic Task)
- **Agent**: `generalist`
- **Task**: 
    - [x] Freeze requirements from `.venv_legacy` and `.venv_vllm_017`.
    - [x] Isolate core legacy packages (`chromadb`, `nemo-toolkit`, `playwright`, `mcp`).
    - [ ] `pip install` core packages into the new `.venv`, allowing `pip` to resolve sub-dependencies.
- **Verification**: `pip list` in the new `.venv` must show all critical packages.

### Phase 2: Playwright Binary Verification
- [ ] **Tool**: `HomeLabAI/.venv/bin/playwright install`
- **Goal**: Ensure the headless browser binaries are downloaded and executable within the new consolidated environment.

### Phase 3: Orchestration Hardening
- [ ] **Update Service File**:
    - **Target:** `/etc/systemd/system/lab-attendant.service`
    - **Action:** Ensure `ExecStart` points *exclusively* to `/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3`.
- [ ] **Daemon Reload**:
    - **Tool:** `sudo systemctl daemon-reload`

### Phase 4: Decommissioning (The Point of No Return)
- **Conductor Track**: `decommission-legacy-venvs`
- [ ] **Add to `.gitignore`**: Add `.venv*/` and `*.venv/` to `HomeLabAI/.gitignore` to prevent accidental tracking.
- [ ] **The Purge**: 
    - **Command:** `rm -rf HomeLabAI/.venv_legacy HomeLabAI/.venv_vllm_017 .venv_vllm_017`
    - **Rationale:** Prevents future "Split-Brain" temptations.

### Phase 5: Final Shakedown
- [ ] **Restart Service**: `sudo systemctl restart lab-attendant.service`
- [ ] **Trigger Ignition**: Manually trigger `POST /ignition` via `curl` or dashboard.
- [ ] **Physician's Gauntlet**: Execute the full test suite (`pytest src/tests/`) to confirm 100% operational parity.

---

## ⚠️ Predicted Pain Points
1.  **`pip` Resolution Hell**: A sub-dependency could still have a hard version pin. 
    *   **Debug Tool**: Manually inspect `/tmp/combined_reqs.txt` and use `pip install <package> --dry-run`.
2.  **`$PATH` Contamination**: The agent's shell environment could interfere.
    *   **Debug Tool**: Explicitly call the venv Python: `/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3 ...`
3.  **Permissions**: `sudo` might be required for `systemctl` or file operations. The `generalist` will need to be granted permissions if necessary.

---
**"One environment to rule them all."**
