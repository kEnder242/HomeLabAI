# Home Lab AI: Project Status (Mar 6, 2026)

## Current Core Architecture: v4.5 "Autonomous Residency"
*   **Orchestration**: Managed via **`lab-attendant.service` (systemd)**.
    *   **Safe-Pilot [FEAT-136]**: Autonomous Lab ignition post-boot with VRAM safety gate.
    *   **The Assassin [FEAT-119]**: Atomic port-reaping and PGID process termination.
    *   **Lab Fingerprint [FEAT-121]**: Distributed tracing for RAM-to-Disk parity.
*   **The Communication Hub (Corpus Callosum)**:
    *   **Unified Base Model [FEAT-030]**: Standardized on **Llama-3.2-3B-AWQ** for residency; **Qwen-2.5-27B** for synthesis.
    *   **vLLM 0.16.0 Breakthrough**: Successfully bypassed Turing (2080 Ti) VRAM constraints using `lo` loopback handshakes.
    *   **Non-Blocking Dispatch**: Immediate streaming of node responses.
*   **Synthesis Pipeline**:
    *   **Strategic Anchoring [FEAT-128]**: Extraction of career-level focal points.
    *   **Robust Extraction [FEAT-131]**: Regex fallback for conversational LLM parsing.

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | Version 550.120 (CUDA 12.4) |
| **Lab Attendant** | ✅ STABLE | [FEAT-119/121/136] Safe-Pilot autonomous boot active. |
| **Bicameral Hub** | ✅ READY | Standardized on 120s timeouts for reasoning. |
| **Synthesis Burn** | ✅ HARDENED | [FEAT-130/131] Robust JSON & Atomic state active. |
| **EarNode (STT)** | ✅ STABLE | NeMo resident; Barge-In logic verified. |

## Active Sprint: SPR-11-05 "Semantic Re-Mapping" (Feb 27, 2026)
**Objective: Ingest high-fidelity career META documents and implement Strategic Anchoring.**
**Current Sprint:** **[Sprint Plan: Semantic Re-Mapping](../Portfolio_Dev/SEMANTIC_RE_MAPPING.md)**

**Status Summary:**
*   **Phase A (Parity)**: [COMPLETE] Absolute pathing and timeout hardening standing.
*   **Phase B (Synthesis)**: [ACTIVE] Ported strategic prompts and DOCX support.
*   **Phase C (Grounding)**: [COMPLETE] Archaeological mapping (2005-2024) verified.

*Refer to the Feature Tracker for permanent technical DNA.*
