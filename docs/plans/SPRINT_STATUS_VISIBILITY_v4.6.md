# Sprint Plan: Status Visibility & Pager Restoration [v4.6]
**Status:** ACTIVE
**Goal:** Restore high-fidelity interactive logging, Recruiter report visibility, and implement "The Physician's Gauntlet" deep hardening.

---

## 🏎️ 1. The Why
The current `status.html` is "neutered." It provides metadata but lacks the interactive depth required for a "Physician's Ledger." We must transition from path-testing to behavioral-testing while maintaining our "Class 1" (no framework) philosophy.

## 🧪 2. Core Logic: Interactive Pager
**Target**: `Portfolio_Dev/field_notes/status.html`

### **The "Blue Tree" Port**:
*   **Rationale**: Enable structured triage of lab events without gapping to the terminal.
*   **Mechanism**: Port hierarchical expansion from `timeline.html`.
*   **Markdown Viewer**: Use `marked.js` (off-the-shelf, single-file) to render `job_brief_*.md` files directly in the dashboard.

---

## 🤕 3. Recovered Gems (The Feb 15 Restoration)
These features were lost in the mania and will be restored during this sprint:
*   **[FEAT-045] Neural Pager Interactivity**: Professional color-coded alerts and raw evidence viewing.
*   **[FEAT-078] Neural Trace**: Automatic JSON logging of all Brain/Pinky payloads for debugging.

---

## 📅 4. Re-ordered Tasks (BKM-020 Standards)

### Task 10: Recruiter Path Hardening
*   **Why**: Ensure artifacts are web-accessible and persistent on the SSD.
*   **How**: Align `recruiter.py` storage paths to `Portfolio_Dev/field_notes/data/recruiter_briefs/`.
*   **Proof**: `test_status_integration.py` confirms file existence on SSD and correct Pager registration.

### Task 11: Neural Trace (Inference Mirror) [FEAT-078]
*   **Why**: To provide an immutable "Black Box" record for hallucination forensics.
*   **How**: Re-enable the black-box logging of all AI payloads to `trace_*.json` in the `loader.py` decorator.
*   **Proof**: Forensic JSONs are generated for every inference turn.

### Task 8: Restore High-Fidelity Pager UI [FEAT-045]
*   **Why**: To provide visual triage cues for silicon health and recruitment events.
*   **How**: Implement color-coded alerts (Red/Orange/Blue) and the "Blue Tree" hierarchical expansion logic in `status.html`.
*   **Proof**: Clicking a log entry successfully reveals the underlying telemetry data.

### Task 9: Implement Markdown Brief Viewer [FEAT-116]
*   **Why**: To make Recruiter findings readable without leaving the dashboard using a standardized library.
*   **How**: Integrate `marked.js` into `status.html` to fetch and render `job_brief_*.md` files.
*   **Proof**: Selecting a Recruiter log displays the rendered Markdown content.

### Task 15: Update Script Map
*   **Why**: Maintain the "Physician's Ledger" accuracy.
*   **How**: Add Tasks 12, 13, and 14 to `HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md`.
*   **Proof**: `cat DIAGNOSTIC_SCRIPT_MAP.md` shows the new gauntlet tests.

### Task 12: Grounding Fidelity Test
*   **Why**: Prove the Brain is using retrieved history instead of hallucinations.
*   **How**: Write `src/debug/test_grounding_fidelity.py`. Verifies that Brain responses contain unique technical anchors from the RAG context.
*   **Proof**: Test fails if Brain mentions generic scenarios not present in logs.

### Task 13: Consensus Loop Stress-Test
*   **Why**: Verify the "Internal Debate" improves technical synthesis quality.
*   **How**: Write `src/debug/test_consensus_loop.py`. Triggers debate and has the Architect node evaluate the synthesis.
*   **Proof**: Validated synthesis of conflicting viewpoints.

### Task 14: Deep Smoke Cycle
*   **Why**: Verify full system state-machine (Cycle of Life).
*   **How**: Implement `acme_lab.py --mode DEEP_SMOKE`. Executes: Ingest -> Reason -> Dream -> Verify Recall.
*   **Proof**: Successful end-to-end traversal without crashes.

---
*Reference: [HomeLabAI/docs/Protocols.md](../Protocols.md)*
