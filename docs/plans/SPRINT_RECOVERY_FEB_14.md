# 🏃 Sprint Plan: Project "Resurrection" (Feb 14, 2026)
**"Recovering the Lost Gems & Hardening the Silicon"**

## 🎯 Objective
To restore high-value strategic tools lost during the v3.5 refactor, optimize VRAM efficiency via Liger-Kernels, and enforce hemispheric directness in the Bicameral Mind. This sprint prioritizes **Silicon Stability** and **Agentic Utility**.

---

## 🩺 Diagnostic Resources
Before executing any verification tasks, refer to the **[Diagnostic Rundown Ledger](../DIAGNOSTIC_RUNDOWN.md)** for detailed tool goals and pass/fail criteria.

---

## 🏎️ Phase 1: Silicon Baseline (Liger + Apollo)
**Goal:** Achieve high-throughput inference with < 10.5GB VRAM peak.

*   **Task 1.1: Liger Restoration.** Modify `src/vllm_liger_server.py` to re-enable Liger-Kernels for AWQ model acceleration.
*   **Task 1.2: Apollo Profiling.** Run `src/debug/test_apollo_vram.py` to perform a "Token Burn" (KV cache allocation).
*   **Task 1.3: Characterization.** Generate `vram_characterization.json` to define "Safe Tiers" for the Attendant.
*   **Verification:** `src/test_liger.py` must pass with zero silicon errors.

## 🔪 Phase 2: Strategic Tool Restoration (The Scalpel Pass)
**Goal:** Restore the agent's ability to interact with the 18-year archive and personal history.

*   **Task 2.1: Port CV Builder.** Integrate `build_cv_summary` into `BicameralNode`.
*   **Task 2.2: Port BKM Generator.** Integrate `generate_bkm` for automated technical documentation.
*   **Task 2.3: Port Archive Access.** Restore `access_personal_history` and `start_draft` tools.
*   **Verification:** `src/debug/test_tool_registry.py` must confirm all 4 tools are visible and callable.

## 🎭 Phase 3: Persona Hardening (TTL + Amygdala)
**Goal:** Fix the "Narf Loop" and improve interjection quality.

*   **Task 3.1: Weighted Banter.** Re-implement **Weighted TTL Decay** in `acme_lab.py` reflex loop.
*   **Task 3.2: Complexity Triggers.** Upgrade Amygdala from keyword-matching to **Complexity Matching** (>15 words + technical verbs).
*   **Task 3.3: Verification Gauntlet.** Run `src/debug/test_lifecycle_gauntlet.py` to verify Hub resilience under interjective load.

## 🛡️ Phase 4: Flexible VRAM Guard (SIGTERM Protocol)
**Goal:** Move from brittle hardcoded MiB limits to dynamic pre-emption.

*   **Task 4.1: Dynamic Limits.** Update `lab_attendant.py` to consult characterization data.
*   **Task 4.2: Pre-emption Logic.** Implement the **Flexible SIGTERM Protocol** to suspend engines when non-AI tasks (Games/Transcodes) start.
*   **Verification:** `src/test_vram_guard.py` using simulated silicon pressure.

## 🧠 Phase 5: Brain Refinement (The "Directness" Rule)
**Goal:** Force the Left Hemisphere to answer the user before explaining its reasoning.

*   **Task 5.1: Numeric Enforcement.** Update `BRAIN_SYSTEM_PROMPT` to mandate "Numeric/Factual Result First."
*   **Task 5.2: Hemispheric Crosstalk.** Update the Hub to pass Pinky's "handover vibe" to Brain for context continuity.
*   **Verification:** `src/debug/test_pi_flow.py` (Expecting numeric Pi result, not a Python script description).

---

## 📜 Active Protocols
- **QQ (Quick Question):** Direct answers only. No implementation dives.
- **AFK (Heads Down):** Autonomous continuity mode. HALT only on BKM-004 condition.
- **Discuss with me (BKM-004):** Mandatory halt on silicon/driver errors.
