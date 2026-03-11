# Sprint Plan: [SPR-11-RECRUITER] Multi-Vector Acquisition
**Version:** 1.0 (Phase 11 Synthesis)
**Goal:** Refactor the "Skeleton Recruiter" into a high-fidelity acquisition engine that aligns real-world job openings with the 18-year technical DNA buckets.

## 🎯 The Mission
To move beyond "simulated" job listings. The Lab must use its new **Browser Node** (Playwright) to verify listings and the **Sovereign Brain** (4090) to perform multi-vector alignment scoring against the established Lead Engineer buckets.

---

## 🧬 Architectural Anchors (The "Why")

### 1. The Lost Buckets (Team Signatures)
The recruiter currently ignores the `team_signatures.json` metadata. We must restore alignment with these authoritative DNA pillars:
*   **[BUCKET-01] Telemetry & Observability**: RAPL, MSR, DCGM, Grafana/Prometheus.
*   **[BUCKET-02] SoC Debug & Pre-Silicon**: Simics, JTAG, Intel VISA, Bring-up.
*   **[BUCKET-03] Manageability (Redfish/IPMI)**: OpenBMC, MCTP, PLDM, Firmware.
*   **[BUCKET-04] Python Validation & Automation**: PythonSV, PyTest, Scalable Frameworks.

### 2. Physical Verification (FEAT-168)
*   **Problem**: Current recruiter "hallucinates" URLs or uses hard-coded mocks.
*   **Solution**: Use the **Browser Node** to physically `GET` the Job Description (JD) text, ensuring the listing is real and the content is accessible.

### 3. Lead Engineer Match (The "Sovereign Audit")
*   **Mechanism**: The Brain (4090) evaluates the JD text against the **Rank 4 "Diamond Gems"** in the archive. 
*   **Output**: Instead of a "Match Score," the recruiter provides **"Evidence of Alignment"** (e.g., *"This role requires MCTP debugging, which matches your 2022 Aurora execution history."*)

---

## 🛠️ Implementation Tasks

### PHASE 1: The Scout (Infrastructure)
- [ ] **[RE-FEAT-168.1] Browser Node Scaffolding**: 
    - Implement `src/nodes/browser_node.py` using Playwright.
    - Tool: `browse_url(url)` -> returns clean markdown of page content.
- [ ] **[RE-FEAT-168.2] JD Verification**:
    - Update `recruiter.py` to verify every LLM-discovered URL via the Scout.
    - Discard 404s, expired listings, or gated login walls.

### PHASE 2: The Auditor (Logic)
- [ ] **[RE-FEAT-167.1] Multi-Vector Scoring Refactor**:
    - Replace the basic keyword counter in `calculate_match_score` with a Brain-driven semantic pass.
    - Input: Verified JD text + `team_signatures.json`.
    - Output: Bucket-specific alignment scores.
- [ ] **[RE-FEAT-167.2] DNA Evidence Mapping**:
    - Task the Brain with finding the "Matching Scar" for every top target.
    - Query the Archive Node for specific gems matching the JD's requirements.

### PHASE 3: The Brief (Synthesis)
- [ ] **[UI-042] Bucket-Aware Job Brief**:
    - Refactor `generate_brief` to group jobs by **Team Signature Bucket**.
    - Add a "Lead Engineer Audit" section for each job, explaining the match.
- [ ] **[UI-043] Dashboard Reporting**:
    - Update `recruiter_report.json` to include bucket-level density (e.g., "3 Telemetry matches, 1 SoC Debug match").

---

## 🧪 Verification & Gauntlet
*   **Live Fire Test**: Execute `run_recruiter_task` and verify the brief contains real text from an NVIDIA Workday JD.
*   **DNA Pass**: Verify that the "Evidence of Alignment" correctly references projects like **VISA**, **Aurora**, or **Montana**.

---

## 🏺 Recovered Gems (Technical Logic)
*   **Anchor**: `HomeLabAI/config/team_signatures.json` (Primary source for bucket definitions).
*   **Anchor**: `HomeLabAI/config/recruiter_config.json` (Target sites and roles).
*   **Gem**: Use the `extract_json_from_llm` regex pattern from `nibble_v2.py` to ensure Brain-driven scoring is robust against conversational drift.

---
**"Don't just find a job; acquire the next technical milestone."**
