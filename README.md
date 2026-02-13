# HomeLabAI: A Distributed Voice-Native Ecosystem (v3.5)

**HomeLabAI** is a proactive, voice-first AI ecosystem designed for the modern home lab. It functions as a distributed agentic partner—integrating Linux servers, Windows workstations, and personal knowledge bases—to act as a highly specialized, context-aware "Jarvis."

---

## 🏗️ The Acme Lab Model: Architecture
HomeLabAI employs the **Bicameral Mind** pattern—an asynchronous dispatch model that distributes cognitive load across specialized nodes.

### 1. The Lab Attendant (Immutable Bootloader)
*   **Role:** Lifecycle management and hardware monitoring.
*   **VRAM Guard:** Dynamically selects reasoning engines (vLLM, Ollama, or Stub) based on real-time GPU headroom via DCGM/Prometheus.
*   **Service:** Managed via `lab-attendant.service` (Systemd).

### 2. The Communication Hub (`acme_lab.py`)
*   **Role:** The **Corpus Callosum**. An asynchronous orchestrator that manages multiple interjective streams:
    *   **Reflex Loop:** Background character tics and environmental alerts.
    *   **Sentinel Mode:** Proactive Brain interjections based on silicon-level keywords.
    *   **Banter System:** Hemispheric interaction with weighted TTL decay.

### 3. The Strategic Workbench
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
*   **v3.5.x:** Implemented Asynchronous Dispatch, VRAM Guard, and Patch-based editing.
*   **v3.4.x:** Stabilized EarNode (NeMo) and resident initialization.
*   **Jan 2026:** Rebranded as HomeLabAI; refined the "Bicameral Mind" (Acme Lab) architecture.
