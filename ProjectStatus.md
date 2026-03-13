# Home Lab AI: Project Status (Mar 13, 2026)

## Current Core Architecture: v5.0 "Silicon Stability"
*   **Orchestration**: Managed via **`lab-attendant-v2.py` (systemd)**.
    *   **Bilingual Attendant (V2) [FEAT-156]**: Dual REST/MCP support with SSE hot-linking.
    *   **The Assassin [FEAT-119]**: Atomic port-reaping and PGID process termination.
    *   **Lab Fingerprint [FEAT-121]**: Boot Hash & Git-Commit tracing active.
*   **The Communication Hub (Bicameral Resonance)**:
    *   **Unified Base Model [FEAT-030]**: Standardized on **Llama-3.2-3B-AWQ** for residency.
    *   **Neural Resonance [FEAT-182]**: Pinky-to-Brain inter-agent overhearing logic active.
    *   **Behavioral DNA [FEAT-181]**: Semanticexpert routing via ChromaDB vibes.
*   **Synthesis Pipeline**:
    *   **Cumulative Synthesis [FEAT-127]**: Layered history + de-duplication active.
    *   **Safe-Scalpel [FEAT-198]**: Atomic, lint-gated code patching via MCP.

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | Version 550.120 (CUDA 12.4) |
| **Lab Attendant** | ✅ STABLE | [FEAT-156] SSE Hot-Link and [FEAT-119] Assassin active. |
| **Bicameral Hub** | ✅ READY | [FEAT-181/182] Resonant Vibe active. |
| **EarNode (STT)** | ✅ STABLE | NeMo resident; Load-first VRAM prioritization [FEAT-145]. |

## Active Sprint: SPR-13.0 "Silicon Stability" (Mar 13, 2026)
**Objective: Resolve VRAM instability on vLLM 0.17 and restore the Resilience Ladder.**
**Current Sprint:** **[Sprint Plan: Silicon Stability](../Portfolio_Dev/SPRINT_PLAN_SPR_13_0.md)**

**Status Summary:**
*   **Phase A (Parity)**: [COMPLETE] Absolute pathing and timeout hardening standing.
*   **Phase B (Synthesis)**: [ACTIVE] Ported strategic prompts and DOCX support.
*   **Phase C (Grounding)**: [COMPLETE] Archaeological mapping (2005-2024) verified.

*Refer to the Feature Tracker for permanent technical DNA.*
