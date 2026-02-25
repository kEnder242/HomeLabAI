# Sprint Plan: Status Visibility & Pager Restoration [v4.6]
**Status:** ACTIVE
**Goal:** Restore high-fidelity interactive logging and Recruiter report visibility in `status.html`.

---

## 🏎️ 1. The Why
The current `status.html` is "neutered." It provides metadata but lacks the interactive depth required for a "Physician's Ledger." We lost severity-based UI jitters, source filtering, and the ability to read the "Evidence" behind a log entry.

## 🧪 2. Core Logic: Interactive Pager
**Target**: `Portfolio_Dev/field_notes/status.html`

### **The "Blue Tree" Port**:
*   **Logic**: Port hierarchical expansion from `timeline.html`.
*   **Expansion**: Clicking a "Recruiter" log should fetch and render the corresponding Markdown brief from `/data/recruiter_briefs/`.
*   **Evidence**: Clicking a "Hardware" log should reveal the raw `nvidia-smi` or `DCGM` telemetry used for the alert.

---

## ⚡ 3. Recruiter Path Alignment
**Target**: `HomeLabAI/src/recruiter.py`
*   **Action**: Update the output path for generated MD briefs to the web-accessible `Portfolio_Dev/field_notes/data/recruiter_briefs/`.
*   **Log Consolidation**: Ensure `recruiter.log` is written to the same directory for direct UI tailing.

---

## 🤕 4. Recovered Gems (The Feb 15 Restoration)
These features were lost in the mania and will be restored during this sprint:
*   **[FEAT-045] Neural Pager Interactivity**: Pulsing alerts and raw evidence viewing.
*   **[FEAT-078] Forensic Mirroring**: Automatic JSON logging of all Brain/Pinky payloads for debugging.

---

## 📅 5. Tasks
- [ ] **Task 8: Restore High-Fidelity Pager UI.** Implement pulsing alerts, jitter for `CRITICAL`, and source filtering.
- [ ] **Task 9: Implement Markdown Brief Viewer.** Create interactive expansion logic to read `job_brief_*.md` files directly in the dashboard.
- [ ] **Task 10: Recruiter Path Hardening.** Align `recruiter.py` with the new web-accessible storage paths.
- [ ] **Task 11: Forensic Mirroring.** Re-enable the black-box logging of AI payloads.

---
*Reference: [HomeLabAI/docs/Protocols.md](../Protocols.md)*
