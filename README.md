# HomeLabAI: A Distributed Voice-Native Ecosystem (v4.1)

**HomeLabAI** is a proactive, voice-first AI ecosystem designed for the modern home lab. It functions as a distributed agentic partner—integrating Linux servers, Windows workstations, and personal knowledge bases—to act as a highly specialized, context-aware "Jarvis."

## 🔭 The High-Level Vision
The project is built on the philosophy that a personal AI should be a synthesis of four distinct technical roles, coordinated by a sentient sentinel:

*   **The Sensory Lead (EarNode):** Powered by **NVIDIA NeMo (STT)**, it provides always-on listening. It is loaded first to prevent memory fragmentation, though it may be unloaded in future resource-priority scenarios.
*   **Lab:** The **Environmental Sentinel**. Monitors the "4th Wall" (Hardware vitals, Silicon limits) and coordinates the hemispheres.
*   **Pinky:** The **Physicality Auditor (Foil)**. Grounds strategic derivations in hardware reality (VRAM, Thermals) using AYPWIP-style literalism.
*   **Brain:** The **Sovereign Architect (4090)**. High-fidelity reasoning and archive synthesis using the Qwen 27B Ultra tier.
*   **Architect:** The **Structural Registrar**. Resident BKM Librarian responsible for high-density formatting of derivations into the BKM Protocol [v3.0] format.

### The "Talk & Read" Philosophy
*   **Voice Input:** Optimized for speed and natural brainstorming.
*   **Text Output:** Designed for rapid scanning and information density.
*   **The Loop:** A tight, low-latency feedback loop that facilitates seamless collaboration between human and machine.

---

## 🏗️ The Acme Lab Model: Architecture
HomeLabAI employs the **Bicameral Mind** pattern—an asynchronous dispatch model that distributes cognitive load across specialized nodes.

### 1. The Lab Attendant (Bilingual V2)
*   **Role:** Lifecycle management and hardware monitoring.
*   **Dual-Protocol:** Supports **REST (:9999)** for systemd compatibility and **MCP** for native Agentic tool integration.
*   **VRAM Guard:** Detects "Phone Rings" (Socket activity) and "Alarm Clocks" (Scheduled tasks) to manage VRAM. 
*   **Resource Priority:** Ready to issue SIGTERM to AI engines if non-AI tasks (Games/Transcodes) request the silicon.

### 2. The Communication Hub (Corpus Callosum)
*   **Role:** The **Hub**. An asynchronous bridge managing multiple interjective streams:
    *   **The "Unified" Mind:** vLLM-powered state where all resident nodes share the **Unified 3B Base Model** footprint.
    *   **Sentinel Mode:** Proactive Brain interjections based on **Contextual Worthiness** (Amygdala v3) rather than brittle keywords.
    *   **Resilience:** Native NVML telemetry enforcing the **Resilience Ladder** (vLLM -> Ollama -> Downshift -> Suspend).
    *   **The Nightly Recruiter:** Scheduled "Alarm Clock" task matching job openings against the 18-year archive and 3x3 CVT.

### 3. Operational Protocols (Laws of the Lab)
*   **The Montana Protocol:** Mandatory logger isolation. All resident nodes must use `reclaim_logger()` after importing heavy libraries to prevent stdout/stderr hijacking.
*   **The BKM Protocol:** All technical reports and achievement logs must follow the **Execution / Validation / Scars** format to maintain high-density information pedigree.

---

## 📜 Research & Ledger
Refer to internal documentation for technical deep-dives:
*   **[Bicameral DNA Ledger](../Portfolio_Dev/FeatureTracker.md):** The God-View of active technical capabilities.
*   **[Bicameral Dispatch](../Portfolio_Dev/docs/BICAMERAL_DISPATCH.md):** The "Soul" and Persona Architecture.
*   **[Observational Memory](../Portfolio_Dev/docs/RESEARCH_NOTES.md):** Research notes on the transition from RAG to state-based world models.
*   **[vLLM Integration](docs/plans/VLLM_INTEGRATION_PLAN.md):** The iterative path to high-throughput reasoning.
*   **[Resurrection Retrospective](docs/RETROSPECTIVE_AWAKENING_v4.9.md):** The "Lost Gems" recovery log and restoration plan.
*   **Collaborative Workspace:** Unified Diff-based editing via the `patch_file` tool.
*   **Human Priority:** Typing collision awareness suppresses agent tics during active work.
*   **Manual Save:** The `💾 SAVE` event triggers a hemispheric "vibe check" on user edits.

### 4. The Archives (Memory)
*   **Neural Pedigree Recall:** Driven by LoRA-hardened weights encoding 18 years of technical history directly into the model's neurons.
*   **Research Goal: Observational Memory:** Transitioning from RAG lookup to a state-based "World Model" summarized in `compressed_history.json`.
*   **Adaptive Caching:** Semantic cache for high-frequency reasoning results.

---

## 🚀 Getting Started

### 1. Environment Topology
*   **Orchestration Node (Z87-Linux):** Manages STT (NeMo), Pinky, and the Lab Attendant.
*   **Inference Node (Windows 4090):** High-power reasoning host running Ollama/vLLM.

### 2. Execution
The system is managed by the Lab Attendant. Use the native `acme_attendant` MCP tools:
```bash
# Verify the mind is resident
acme_attendant lab_heartbeat

# Start the mind (Unified 3B Base)
acme_attendant lab_start
```

### 3. Client Access
Access the **Web Intercom** via the Portfolio dashboard (port 9001). 
Features multi-panel routing: **Pinky Console** (Gateway) and **Brain Insight** (Strategic).

---

## 📜 Project State
*   **v4.1 (ACTIVE):** Transitioned to **Unified 3B Base (Llama 3.2 / Qwen 2.5)**. Gemma 2 2B tabled due to Turing BF16 hardware incompatibility. Implemented **Monolingual Squeeze** [FEAT-166] for VRAM efficiency.
*   **v4.0:** Implemented the **Resilience Ladder** (Engine Swap & Downshift) for hardware multi-tenancy.
*   **v3.5.x:** Implemented Asynchronous Dispatch, VRAM Guard, and Patch-based editing.
*   **v3.4.x:** Stabilized EarNode (NeMo) and resident initialization.
*   **Jan 2026:** Rebranded as HomeLabAI; refined the "Bicameral Mind" (Acme Lab) architecture.
