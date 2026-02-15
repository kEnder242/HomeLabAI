# HomeLabAI: A Distributed Voice-Native Ecosystem (v3.5)

**HomeLabAI** is a proactive, voice-first AI ecosystem designed for the modern home lab. It functions as a distributed agentic partner—integrating Linux servers, Windows workstations, and personal knowledge bases—to act as a highly specialized, context-aware "Jarvis."

## 🔭 The High-Level Vision
The project is built on the philosophy that a personal AI should be a synthesis of two distinct cognitive styles, modeled after the **Bicameral Mind**:

*   **The Right Hemisphere (Pinky):** Intuitive, Aware, and Presence-focused. This layer manages the "Vibe," sensory input/output, and immediate user interaction.
*   **The Left Hemisphere (The Brain):** Logical, Abstract, and Strategic. This layer manages the "Truth," complex planning, and deep reasoning.

### The "Talk & Read" Philosophy
*   **Voice Input:** Optimized for speed and natural brainstorming.
*   **Text Output:** Designed for rapid scanning and information density.
*   **The Loop:** A tight, low-latency feedback loop that facilitates seamless collaboration between human and machine.

---

## 🏗️ The Acme Lab Model: Architecture
HomeLabAI employs the **Bicameral Mind** pattern—an asynchronous dispatch model that distributes cognitive load across specialized nodes.

### 1. The Lab Attendant (Immutable Bootloader)
*   **Role:** Lifecycle management and hardware monitoring.
*   **VRAM Guard:** Detects "Phone Rings" (Socket activity) and "Alarm Clocks" (Scheduled tasks) to manage VRAM. 
*   **Resource Priority:** Ready to issue SIGTERM to AI engines if non-AI tasks (Games/Transcodes) request the silicon.

### 2. The Communication Hub (Corpus Callosum)
*   **Role:** The **Hub**. An asynchronous bridge managing multiple interjective streams:
    *   **The "Unified" Mind:** vLLM-powered state where all reasoning nodes share the **Gemma 2 2B** base model.
    *   **Sentinel Mode:** Proactive Brain interjections based on **Contextual Worthiness** (Amygdala v3) rather than brittle keywords.
    *   **Resilience:** Native NVML telemetry enforcing the **Resilience Ladder** (vLLM -> Ollama -> Downshift -> Suspend).
    *   **The Nightly Recruiter:** Scheduled "Alarm Clock" task matching job openings against the 18-year archive and 3x3 CVT.

### 3. The Strategic Workbench
...

## 📜 Research & Ledger
Refer to internal documentation for technical deep-dives:
*   **[Bicameral Dispatch](../Portfolio_Dev/docs/BICAMERAL_DISPATCH.md):** The "Soul" and Persona Architecture.
*   **[vLLM Integration](docs/VLLM_INTEGRATION_PLAN.md):** The iterative path to high-throughput reasoning.
*   **[Observational Memory](../Portfolio_Dev/docs/RESEARCH_NOTES.md):** Transitioning from RAG to a state-based world model.
*   **Collaborative Workspace:** Unified Diff-based editing via the `patch_file` tool.
*   **Human Priority:** Typing collision awareness suppresses agent tics during active work.
*   **Manual Save:** The `💾 SAVE` event triggers a hemispheric "vibe check" on user edits.

### 4. The Archives (Memory)
*   **Observational Memory:** Transitioning from RAG lookup to a state-based "World Model" summarized in `compressed_history.json`.
*   **Adaptive Caching:** Semantic cache for high-frequency reasoning results.

---

## 🚀 Getting Started

### 1. Environment Topology
*   **Orchestration Node (Z87-Linux):** Manages STT (NeMo), Pinky, and the Lab Attendant.
*   **Inference Node (Windows 4090):** High-power reasoning host running Ollama/vLLM.

### 2. Execution
The system is managed by the Lab Attendant. Use the HTTP API or the copilot shell:
```bash
# Start the mind
curl -X POST http://localhost:9999/start -H "Content-Type: application/json" -d '{"engine": "OLLAMA"}'
```

### 3. Client Access
Access the **Web Intercom** via the Portfolio dashboard (port 9001). 
Features multi-panel routing: **Pinky Console** (Gateway) and **Brain Insight** (Strategic).

---

## 📜 Project State
*   **v4.0 (ACTIVE):** Transitioned to **Unified Base (Gemma 2 2B)** for all 2080 Ti nodes. Implemented the **Resilience Ladder** (Engine Swap & Downshift) for hardware multi-tenancy.
*   **v3.5.x:** Implemented Asynchronous Dispatch, VRAM Guard, and Patch-based editing.
*   **v3.4.x:** Stabilized EarNode (NeMo) and resident initialization.
*   **Jan 2026:** Rebranded as HomeLabAI; refined the "Bicameral Mind" (Acme Lab) architecture.
