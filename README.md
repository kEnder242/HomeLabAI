# HomeLabAI: A Bicameral Agentic Workspace & Research Playground

HomeLabAI is a federated cognitive sandbox and archive refinement laboratory. It operates as a distributed agentic workspace—integrating Linux hosts, Windows compute nodes, and historical knowledge bases—to facilitate low-latency research, semantic memory extraction, and automated telemetry analysis.

---

## The High-Level Vision: Bicameral Mind Topology

The workspace coordinates cognitive tasks across specialized functional nodes, modeled after the split-brain architecture of the Bicameral Mind:

*   **The Heart (EarNode):** The invariant sensory core. Powered by NVIDIA NeMo (STT), it provides always-on audio capture and mono 16kHz PCM streaming. Sensing is the invariant constant of the lab; reasoning is secondary.
*   **The Right Hemisphere (Pinky):** The Pragmatic Foil. Grounded in physical telemetry, presence-awareness, and immediate user interaction. This layer manages the "Vibe"—evaluating hardware limitations (VRAM, thermals) using AYPWIP-style literalism.
*   **The Left Hemisphere (The Brain):** The Sovereign Architect. Strategic, abstract, and logical. Resident on the compute node, this layer manages the "Truth"—handling long-term archive retrieval, complex code generation, and strategic reasoning (powered by Qwen 27B / Unified 3B tiers).
*   **The Systems Guardian (Lab Attendant):** The lifecycle manager. A systemd-managed daemon that controls engine states, manages the VRAM hardware mutex, and prevents hardware thrashing.
*   **The Structural Registrar (Architect):** The BKM Librarian responsible for formatting technical derivations into the structured BKM Protocol format.

### Operational Philosophy: Multi-Modal Stream Separation
*   **Input Interface:** Optimized for fast, multi-modal command ingestion (both voice and text terminal inputs).
*   **Output Delivery:** Optimized for high-density, rapidly scannable text outputs.
*   **Reasoning Loop:** A tight, low-latency feedback loop ensuring human control over the autonomous synthesis cycles.

---

## The Meta-Agentic Loop: An AI Development Framework

Developing HomeLabAI using a co-pilot (AGY/Gemini) forms a self-refining, meta-agentic loop. The workspace is not merely a collection of scripts, but a self-documenting agentic framework driven by four core document assets:

1.  **The Agentic Contract (docs/Protocols.md):** Defines the operational rules of engagement for the co-pilot (such as the BKM-004 QQ halt protocol, BKM-006 Heads Down continuity, BKM-009 Checkpointing, and BKM-011 Safe-Scalpel gating). This ensures the assistant acts as a predictable engineering partner.
2.  **The DNA Matrix (Portfolio_Dev/FeatureTracker.md):** Records active technical capabilities and "Scars"—retrospectives of past engineering failures and hardware constraints (e.g., vLLM BF16 initialization deadlocks on Turing compute). This serves as a durable context anchor that prevents the agent from repeating past regressions.
3.  **The Instrument Ledger (docs/DIAGNOSTIC_SCRIPT_MAP.md):** Catalogues every validation script and test harness, allowing the agent to run verification cycles (such as test_intent_recall.py for semantic intent or test_sandbox.py for tool isolation) before committing logic.
4.  **The Physical Floor (docs/LAB_INFRASTRUCTURE.md):** Tracks hardware mounts, CUDA drivers, absolute paths, and port mappings.

---

## Portfolio Integration & Static Synthesis

The HomeLabAI execution environment coordinates with the static portfolio repository (Portfolio_Dev):

*   **Static Airlock:** The public gateway (www.jason-lab.dev) hosted on GitHub Pages, linking securely to Zero Trust subdomains.
*   **The Notes Dashboard (notes.jason-lab.dev):** Hosted locally on port 9001 and secured via Cloudflare Access. Provides unified navigation across the Career Timeline, Career Map, and search indexes.
*   **WebSocket Intercom:** A browser-based web panel hosted on the static notes site that initiates secure, real-time WebSocket handshakes back to the local Foyer Router.

---

## Research Grounding

HomeLabAI maps academic literature directly to operational code modules (documented in docs/plans/RESEARCH_SYNTHESIS.md):

*   **FS-Researcher** (Dual-Agent Context/Report generation) $\rightarrow$ implemented via `nibble.py` (Context Builder).
*   **Agentic-R** (Utility-based retrieval ranking) $\rightarrow$ implemented via `ArchiveMemory` ranking.
*   **Apple CLaRa** (Semantic log compression) $\rightarrow$ implemented via `SemanticCondenser` log compression.
*   **Dreaming** (Subconscious memory compilation) $\rightarrow$ implemented via background `dream_cycle.py` summaries.
*   **Internal Debate** (Moderated Byzantine consensus) $\rightarrow$ implemented via `delegate_internal_debate` reasoning.

---

## Project State & Gem Restoration

*   **Version 4.1 (Active):** Standardized on Llama-3.2-3B-AWQ as the Unified Base Model. Implemented Monolingual Squeeze for VRAM efficiency and dynamic sandbox tool isolation.
*   **Gems Restoration Plan (docs/RETROSPECTIVE_AWAKENING_v4.9.md):** Recovering uncommitted logic "Gems" from the log forensics, such as the VRAM Heartbeat (sliding-window load monitoring for graceful model dimming) and Shadow Dispatch (background inference during user typing).
*   **Version 4.0:** Implemented the Resilience Downshift Ladder (vLLM -> Ollama -> Downshift -> Suspend) for hardware multi-tenancy.
*   **Version 3.5:** Standardized asynchronous dispatch and VRAM guard controls.
*   **January 2026:** Rebranded to HomeLabAI; introduced the Bicameral Mind split.
