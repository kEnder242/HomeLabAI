# Sprint Plan: Forensic Hardening [v4.4]
**Status:** DRAFT | **Priority:** High | **Owner:** Gemini CLI (Agent)

## 🎯 Goal
To transition from "Active Construction" to "Forensic Hardening." We will map the project's DNA (Feature Tracker), ground ourselves in the existing codebase and tools, and then surgically refactor the Silicon Hygiene and Watchdog logic to ensure 100% reliability under the Ollama Standard.

---

## 🏛️ Phase 1: Deep Forensic Mapping (The DNA)
**Objective:** Populate the `FeatureTracker.md` Association Matrix.
- [x] **Task 1.1: Git & CLI Log Audit**: Scoured SESSION_BKM files and git logs for feature origins.
- [x] **Task 1.2: BKM Linkage**: Linked historical scars to `acme_lab.py` and `lab_attendant.py`.
- [x] **Task 1.3: Undocumented Feature ID**: Identified Montana, Strategic Sentinel, Iron Gate, Barge-In, and Zombie Port Recovery.
- [x] **Task 1.4: Association Matrix Update**: FeatureTracker.md updated with IDs [FEAT-031] through [FEAT-035].

## 🔍 Phase 2: Code Grounding & Tool Audit (Mandatory)
**Objective:** Internalize the existing implementation to avoid "Re-writing the Wheel."
- [ ] **Task 2.1: Mapping Document Inventory**: Verified `TOOL_RUNDOWN.md` and `DIAGNOSTIC_RUNDOWN.md` as primary anchors.
- [ ] **Task 2.2: Mode & State Review**: Deep dive into `acme_lab.py` and `lab_attendant.py` to identify all current operational modes (e.g., `SERVICE_UNATTENDED`, `DEBUG_BRAIN`).
- [ ] **Task 2.3: Logic Parity Check**: Review the inventory against the actual source code to verify parity and identify discrepancies.

## 🛠️ Phase 3: Silicon Hygiene & Cruft Cleanup
**Objective:** Surgical refactoring with 100% verification.
> [!IMPORTANT]
> **LINTING MANDATE:** All code changes (patches OR full-file writes) MUST be followed by a `ruff` verification. Use `atomic_patcher.py` whenever possible; if a rewrite is required, run `ruff check <file>` manually before concluding.

- [ ] **Task 3.1: Silicon Logic Refactor**: Decouple `execute_dispatch` from `process_query` in `acme_lab.py`. Remove "vLLM Ghost" variables and legacy initialization deadwood.
- [ ] **Task 3.2: Watchdog Hygiene**: Review `lab_attendant.py` to confirm it has moved beyond PID monitoring and clean up any remaining technical debt or "scars" from the vLLM transition.

---

## 🏺 Bubbled-up Backlog
- **[FEAT-028] Strategic Ping Review**: Revisit the generation probe timeout (currently 5s) and evaluate parallel heartbeat threads.
- **[FEAT-031] Montana Protocol**: Ensure the logger isolation is consistently applied across all new node spawns.
- **[REVERSION] Return to 580 Protocol**: (Planning only) Define the automated cleanup of "Isolation Protocol" artifacts.

---
*Reference: [BOOTSTRAP_v4.3.md](../../BOOTSTRAP_v4.3.md) | [00_FEDERATED_STATUS.md](../../Portfolio_Dev/00_FEDERATED_STATUS.md)*
