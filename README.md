# Acme Lab: Voice-Activated Personal Knowledge Assistant

**Concept:** A "Pinky and the Brain" inspired home lab agent.
**Analogy:** "Acme Labs" is the infrastructure. "Pinky" and "The Brain" are residents (agents) living inside it.

## 🧠 UX Philosophy: "Talk & Read"
We optimize for a specific human-centric workflow: **Voice Input, Text Output.**
*   **Speed:** Speaking is faster than typing. Reading is faster than listening.
*   **Flow:** No waiting for TTS (Text-to-Speech) to drone on. You speak, see the answer instantly, and keep moving.
*   **The Loop:** A tight feedback loop where the AI acts as a "Co-Pilot" you can mutter to while coding.

## 🏗️ Architecture: The Neural Mesh

The system is built as an Event-Driven Mesh using the **Model Context Protocol (MCP)**.

### 1. The Lab (Host)
*   **File:** `src/acme_lab.py`
*   **Role:** The neutral "Event Bus". It connects Equipment (Mic/Speakers) to Residents.
*   **Hardware:** Runs on `z87-Linux` (NVIDIA 2080 Ti).
*   **Tech:** Python `asyncio`, `websockets`, `mcp`.

### 2. The Residents (Nodes)
*   **🐹 Pinky (Persona):** `src/nodes/pinky_node.py`
    *   **Model:** `mistral:7b` (Fast, Local).
    *   **Role:** Triage, Greetings, "Narf!". Decides when to wake the Brain.
*   **🧠 The Brain (Genius):** `src/nodes/brain_node.py`
    *   **Model:** `llama3:70b` (Remote Windows GPU).
    *   **Role:** Deep Reasoning, Coding, Planning.
*   **📚 The Archives (Memory):** `src/nodes/archive_node.py`
    *   **Tech:** ChromaDB, SentenceTransformers.
    *   **Role:** Long-term memory and "CLaRa" session summarization.

### 3. The Equipment
*   **👂 EarNode:** `src/equipment/ear_node.py` (NVIDIA NeMo Streaming ASR).
*   **📢 MouthNode:** (Coming Soon) Piper TTS / WebSocket Frontend.

---

## 🚀 Getting Started

### 1. Environment Orientation
*   **Dev Machine:** Where you edit code (`~/HomeLabAI`).
*   **Target Host:** `jallred@z87-Linux.local` (`~/AcmeLab`).
*   **Windows Host:** `192.168.1.26` (Ollama).

### 2. Deployment
Do not run `acme_lab.py` locally. It requires the Linux GPU environment.
Use the helper script:

```bash
./run_remote.sh [MODE]
```
**Modes:**
*   `SERVICE`: Passive mode. Brain sleeps until called. (Default)
*   `DEBUG_BRAIN`: Forces Brain wake-up on boot.
*   `DEBUG_PINKY`: Local logic only. Brain disconnected.

### 3. Requirements
See `requirements.txt`.
Remote venv: `~/AcmeLab/.venv`

---

## 📜 Credits
*   **JARVIS / Iron Man:** The functional goal.
*   **Pinky & The Brain:** The personality engine.
*   **DeepAgent:** The legacy orchestrator roots.