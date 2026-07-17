# HomeLabAI: A Distributed AI Research Environment

HomeLabAI is a distributed AI system that integrates Linux and Windows machines with historical data to perform research, extract information from memory, and analyze telemetry.

## Architecture Overview: Dual-Component Design

The workspace coordinates cognitive tasks across specialized functional nodes:

*   **Right Hemisphere (Telemetry & Interaction):** Manages physical telemetry, presence, and immediate user interaction, evaluating hardware limitations (VRAM, thermals).
*   **Left Hemisphere (Compute & Reasoning):** Handles long-term data retrieval, complex code generation, and strategic reasoning on the compute node.
*   **The Systems Guardian (Lab Attendant):** The lifecycle manager. A systemd-managed daemon that controls engine states, manages the VRAM hardware mutex, and prevents hardware thrashing.
*   **The Sensory Modality (EarNode):** Always-on audio ears powered by NVIDIA NeMo (STT). Provides audio capture and mono 16kHz PCM streaming.
*   **The Structural Registrar (Architect):** BKM Librarian responsible for formatting technical derivations into the structured BKM Protocol format.

### Operational Philosophy: Multi-Modal Stream Separation
*   **Input Interface:** Optimized for fast, multi-modal command ingestion (both voice and text terminal inputs).
*   **Output Delivery:** Optimized for high-density, rapidly scannable text outputs.
*   **Reasoning Loop:** A tight, low-latency feedback loop ensuring human control over the autonomous synthesis cycles.

---

## AI Development Framework

Developing HomeLabAI with a co-pilot (AGY/Gemini) uses a feedback loop. The workspace is an agentic framework documented by four core assets:

1.  **The Agentic Contract (docs/Protocols.md):** Defines the operational rules of engagement for the co-pilot (such as the BKM-004 QQ halt protocol, BKM-006 Heads Down continuity, BKM-009 Checkpointing, and BKM-011 Safe-Scalpel gating). This ensures the assistant acts as a predictable engineering partner.
2.  **Feature Tracker (Portfolio_Dev/FeatureTracker.md):** Records active technical capabilities and documents past engineering failures and hardware constraints (e.g., vLLM BF16 initialization deadlocks on Turing compute). This prevents the agent from repeating past regressions.
3.  **The Instrument Ledger (docs/DIAGNOSTIC_SCRIPT_MAP.md):** Catalogues every validation script and test harness, allowing the agent to run verification cycles (such as test_intent_recall.py for semantic intent or test_sandbox.py for tool isolation) before committing logic.
4.  **The Physical Floor (docs/LAB_INFRASTRUCTURE.md):** Tracks hardware mounts, CUDA drivers, absolute paths, and port mappings.

---

## Environment & Model Topology

HomeLabAI distributes tasks across co-equal nodes based on physical hardware capacities:

### 1. Orchestration Host (z87-Linux)
*   **Hardware:** NVIDIA RTX 2080 Ti (11GB VRAM, Turing Compute 7.5 architecture).
*   **Constraint:** Turing lacks native `bfloat16` hardware execution units. Running BF16 models on vLLM's custom kernels causes silent driver-level deadlocks.
*   **Unified Base Model:** Standardized on **Llama-3.2-3B-AWQ** running in vLLM. Swapping resident node personas (Pinky, Brain, Librarian, Architect) is handled dynamically via low-overhead LoRA adapters. This shared footprint takes up only ~2.5GB of VRAM, leaving KV cache headroom and space for NeMo STT (EarNode).
*   **Fallback Engine:** Gemma 2 2B is relegated to local Ollama because Ollama natively handles the BF16-to-FP16 casting gracefully on Turing without deadlocking.

### 2. Compute Node (KENDER - 192.168.1.26)
*   **Hardware:** Windows workstation running a high-power RTX 4090.
*   **Model Residency:** Queries to KENDER's Ollama endpoint do not specify a model name, allowing the engine to leverage whatever model is currently resident in VRAM (typically **omnicoder**) to prevent context reloading and VRAM thrashing overhead.

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

## Project State

*   **Version 4.1 (Active):** Standardized on Llama-3.2-3B-AWQ as the Unified Base Model with multi-LoRA switching. Implemented dynamic sandbox tool isolation.
*   **Version 4.0:** Implemented the Resilience Downshift Ladder (vLLM -> Ollama -> Downshift -> Suspend) for hardware multi-tenancy.
*   **Version 3.5:** Standardized asynchronous dispatch and VRAM guard controls.
*   **January 2026:** Rebranded to HomeLabAI; introduced the Bicameral Mind split.
