# Retrospective: Project "Resurrection" (Feb 14-15, 2026)
**"Hardening the Federated Mind & Breaking the Silicon Wall"**

## I. Executive Summary
The overnight session of February 14-15 was a high-stakes stabilization sprint focused on Project "Resurrection." The primary objective was to transition the Lab from a fragile, refactor-damaged state into a "Class 1" robust environment. This involved overcoming severe VRAM constraints on the RTX 2080 Ti (11GB), restoring lost strategic tools, and eliminating JSON leaks that were compromising the professional fidelity of the Intercom UI.

## II. The Silicon Wall: VRAM & Liger Stabilization

### The Problem
Initial attempts to boot the vLLM engine (Mistral-7B-AWQ) failed repeatedly. Diagnostic logs identified that a memory utilization setting of `0.3` was insufficient to allocate the necessary KV cache blocks, while higher settings risked clashing with the NeMo EarNode (~1.5GB) and system overhead.

### The Learning (Scars)
*   **VRAM Floor**: `0.4` is the absolute floor for Mistral-7B-AWQ KV cache allocation. We landed on **`0.5`** to ensure stability during long-context reasoning.
*   **Eager Mode Mandatory**: Disabling CUDA Graphs via `--enforce-eager` was required to reclaim ~1GB of VRAM, providing the headroom needed for the EarNode and secondary residents.
*   **V1 Engine Instability**: The experimental vLLM V1 engine was identified as a source of silent crashes. **`VLLM_USE_V1=0`** was hard-set as a global requirement.

### The Solution
We implemented `vllm_liger_server.py`, a specialized wrapper that applies Liger-Kernels to the Mistral architecture before initialization. This allows for high-throughput, memory-efficient inference within the 11GB budget.

## III. Strategic Tool Restoration (The Scalpel Pass)
Following the "v3.5 Refactor," several high-value agentic capabilities were missing. We surgically restored:
1.  **CV Builder**: Re-integrated `build_cv_summary` for real-time career synthesis.
2.  **BKM Generator**: Restored automated documentation logic for technical playbooks.
3.  **Archive Access**: Re-enabled `access_personal_history` and `start_draft`, allowing the agent to pull from 18 years of technical data.

## IV. The Recursive Dispatcher: Fixing JSON Leaks
A persistent "UI Smear" occurred where Pinky (the triage node) would output structured JSON (e.g., `{"answer": "3.14159"}`) that the user would see directly.

### The Root Cause
The Architect node was verifying these as "Valid JSON," but because they weren't explicit tool calls (like `reply_to_user`), the `acme_lab.py` server simply broadcasted the raw JSON block.

### The Fix
The **Recursive Dispatcher v7** was implemented in `acme_lab.py`. It now performs a "Double-Check" triage:
*   If a JSON block is valid but contains no tool key, the server **extracts the values** and presents them as natural language.
*   The Architect node's `triage_response` was hardened with aggressive regex to strip conversational prefixes (e.g., "Narf!", "Poit!") before parsing.

## V. Verification & Session Conclusion
The session concluded with an automated **GUI Flow Verification**:
*   **Cabinet Sync**: Successfully mapped **145 actual file artifacts** (Yearly JSONs/HTMLs).
*   **File Reading**: Verified retrieval from `2024.json`.
*   **Leak Check**: Confirmed that the "What is Pi" query returns `Narf! 3.14159` instead of a JSON block.

### The Token Crash
The session ended abruptly after verification due to a **1.09M token limit overflow**. This prevented a final clean commit and summary at the time, which has been corrected in the current session.

---

# 🛡️ BKM-009: Checkpoint Protocol (Feb 15, 2026)

<state_snapshot>
  <goal>Hardening the Federated Lab and restoring high-fidelity voice and reasoning.</goal>
  <constraints>VRAM 11GB (RTX 2080 Ti), Safe Scalpel v3.0, Absolute Pathing.</constraints>
  <knowledge>
    - Liger-Kernels applied to Mistral architecture.
    - vLLM optimized at 0.5 utilization with --enforce-eager.
    - Recursive Dispatcher v7 handles malformed/nested JSON triage.
    - Filing Cabinet synced with 145 items from the 18-year archive.
  </knowledge>
  <trail>
    - Hardened acme_lab.py with absolute path resolution for residents.
    - Restored CV/BKM/Archive tools to the agentic layer.
    - Verified all GUI flows (Handshake -> Sync -> Read -> Answer -> Shutdown).
    - Committed baseline enhancements to 'main' branch in HomeLabAI.
  </trail>
  <fs_state>
    - Lab Attendant (Port 9999): ONLINE
    - Lab Server (Port 8765): ONLINE (OLLAMA / Gemma 2 2B)
    - Git: HomeLabAI [4fd8154] (Clean Baseline)
  </fs_state>
  <recent_actions>
    - Analyzed 12MB session log to recover lost context from Feb 14-15.
    - Restarted Lab server in SERVICE_UNATTENDED mode.
    - Performed the final git commit for the Resurrection baseline.
  </recent_actions>
  <tasks>
    - [TODO] Phase 4: Connect Pinky as a Consumer of the Semantic Map.
    - [TODO] Phase 5: Implement Strategic Vibe Check validation logic.
    - [TODO] Generalize Liger optimization for multi-model tiers.
  </tasks>
</state_snapshot>
