# HomeLabAI: A Bicameral Agentic Workspace & Research Playground

HomeLabAI is a federated cognitive sandbox and archive refinement laboratory. It operates as a distributed agentic workspace—integrating Linux hosts, Windows compute nodes, and historical knowledge bases—to facilitate low-latency research, semantic memory extraction, and automated telemetry analysis.

## The High-Level Vision: Bicameral Mind Topology

The workspace coordinates cognitive tasks across specialized functional nodes:

*   **The Sovereign Brain:** Resident on the high-power compute node. Responsible for strategic reasoning, long-term archive retrieval, and complex code generation (powered by Qwen 27B / Unified 3B tiers).
*   **The Pragmatic Foil (Pinky):** Local response node resident on the validation host. Responsible for grounding strategic assertions in physical telemetry (VRAM limits, thermals) using AYPWIP-style literalism.
*   **The Systems Guardian (Lab Attendant):** Systemd-managed lifecycle daemon. Controls engine states, manages the VRAM hardware mutex, and prevents resource thrashing.
*   **The Sensory Modality (EarNode):** Optional voice-input interface powered by NVIDIA NeMo (STT). Provides always-on audio capture and mono 16kHz PCM streaming.
*   **The Structural Registrar (Architect):** BKM Librarian responsible for formatting technical derivations into the structured BKM Protocol format.

### Operational Philosophy: Multi-Modal Stream Separation
*   **Input Interface:** Optimized for fast, multi-modal command ingestion (both voice and text terminal inputs).
*   **Output Delivery:** Optimized for high-density, rapidly scannable text outputs.
*   **Reasoning Loop:** A tight, low-latency feedback loop ensuring human control over the autonomous synthesis cycles.

---

## Portfolio Integration & Static Synthesis

The HomeLabAI execution environment coordinates with the static portfolio repository (Portfolio_Dev):

*   **Static Airlock:** The public gateway (www.jason-lab.dev) hosted on GitHub Pages, linking securely to Zero Trust subdomains.
*   **The Notes Dashboard (notes.jason-lab.dev):** Hosted locally on port 9001 and secured via Cloudflare Access. Provides unified navigation across the Career Timeline, Career Map, and search indexes.
*   **WebSocket Intercom:** A browser-based web panel hosted on the static notes site that initiates secure, real-time WebSocket handshakes back to the local Foyer Router.

---

## Architectural Layout

HomeLabAI distributes tasks across three core components:

### 1. The Lab Attendant (SERVICE_UNATTENDED Mode)
*   **Role:** Node manager and hardware guardian.
*   **Dual-Protocol Interface:** Exposes REST endpoints for systemd control and MCP protocols for agentic tool integration.
*   **VRAM Mutex:** Coordinates VRAM reservation, suspending vLLM instances during heavy gaming/rendering tasks, and enforcing a 60-second quiescence window.

### 2. The Foyer Router (Corpus Callosum)
*   **Role:** Asynchronous WebSocket routing bridge.
*   **Unified Footprint:** Hosts multi-LoRA adapters on top of a single base model (Llama-3.2-3B-AWQ), optimizing the 11GB VRAM budget.
*   **Sentinel Triage:** Routes queries based on semantic vibe classification (TECHNICAL, CASUAL, HISTORICAL, META) and restricts tool availability dynamically.

### 3. Operational Protocols
*   **The Montana Protocol:** Logger reclamation. All nodes must invoke `reclaim_logger()` to prevent STDOUT hijacking by third-party imports.
*   **The BKM Protocol:** Standardization format for engineering playbooks (Execution, Validation, Scars).

---

## Environment Topology

*   **Orchestration Host (z87-Linux):** Native local runner managing the Lab Attendant, Foyer Router, and local resident nodes (Pinky, Lab, Archive).
*   **Compute Node (192.168.1.26):** Remote Windows host running high-throughput vLLM and Ollama inference instances.

### Getting Started

Management is mediated by the Lab Attendant service:

```bash
# Verify process liveness
acme_attendant lab_heartbeat

# Boot the unified inference engine
acme_attendant lab_start
```

---

## Project State

*   **Version 4.1 (Active):** Standardized on Llama-3.2-3B-AWQ as the Unified Base Model. Implemented Monolingual Squeeze for VRAM efficiency and dynamic sandbox tool isolation.
*   **Version 4.0:** Implemented the Resilience Downshift Ladder for engine failover.
*   **Version 3.5:** Standardized asynchronous dispatch and VRAM guard controls.
*   **January 2026:** Rebranded to HomeLabAI; introduced the Bicameral Mind split.
