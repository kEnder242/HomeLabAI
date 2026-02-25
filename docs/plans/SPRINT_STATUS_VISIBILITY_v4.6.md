# Sprint Plan: Status Visibility & Pager Restoration [v4.6]
**Status:** ACTIVE
**Goal:** Restore high-fidelity interactive logging, implement Multi-Stage Retrieval, and deploy the Resonant Oracle.

---

## 🏎️ 1. The Why
The Lab requires a transition from "Metadata" to "Deep Visibility." We need a non-destructive status UI, a way to retrieve raw technical truth (Discovery Pattern) without vector fragmentation, and a professional decoupling of persona from technical signals (Resonant Oracle).

## 🧪 2. Core Logic Refinements

### **The "Blue Tree" UI (Refined)**:
*   **Rationale**: Fix "Long" display and destructive page refreshes.
*   **Mechanism**: CSS overrides for `markdown-body` margins. Refactor `status.html` to use a "Diff-based" DOM update for the log tree.
*   **Proof**: Page polls every 10s without closing open log nodes.

### **[FEAT-117] Multi-Stage Retrieval**:
*   **Rationale**: Prevent hallucination by giving the Brain access to the **Full Raw JSON** once a year/project is discovered.
*   **Mechanism**: Stage 1: ChromaDB lookup. Stage 2: `ArchiveNode` reads the identified local file and extracts the specific entry.
*   **Cross-Hemisphere**: Brain gets raw specs; Pinky gets the abstract for banter.

---

## 📅 3. Tasks (BKM-020 Standards)

### Task 17: Resonant Oracle [FEAT-118]
*   **Why**: Fully decouple persona from logic and remove hard-coded Python strings.
*   **How**: Create `HomeLabAI/config/oracle.json` (The 8-Ball Registry). Update `acme_lab.py` to pick preambles based on Lab state.
*   **Proof**: Brain signals vary based on context and are absent from Python source.

### Task 18: UI High-Density Overhaul
*   **Why**: Improve legibility of the "Physician's Ledger."
*   **How**: Port "Blue Tree" interactivity. Add independent timer for Grafana refresh.
*   **Proof**: No page-flicker during telemetry updates.

### Task 19: The Assassin Logic
*   **Why**: Prevent port 8765 collisions during boot.
*   **How**: Implement port-sniffing and `fuser -k` fallback in `lab_attendant.py`.
*   **Proof**: `run_deep_smoke.py` succeeds even if a ghost Lab is running.

### Task 20: Discovery Pattern Integration [FEAT-117]
*   **Why**: Bridge the gap between vector "discovery" and raw technical "truth."
*   **How**: Update the Amygdala loop to fetch the raw JSON block after a year-trigger.
*   **Proof**: Brain can accurately quote project details found in `2010.json` during a "2010" query.

### Task 21: Update Script Map
*   **Why**: Log today's deep-hardening tests.
*   **How**: Add Gauntlet tests to `HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md`.
*   **Proof**: Map reflects actual 4.6 capabilities.

---
*Reference: [HomeLabAI/docs/Protocols.md](../Protocols.md)*
