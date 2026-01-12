# HomeLabAI: A Distributed Voice-Native Ecosystem

**HomeLabAI** is a proactive, voice-first AI ecosystem designed for the modern home lab. It functions as a distributed agentic partner—integrating Linux servers, Windows workstations, and personal knowledge bases—to act as a highly specialized, context-aware "Jarvis."

By leveraging a hybrid compute model, HomeLabAI achieves low-latency voice interaction without sacrificing the deep reasoning capabilities of large-scale language models.

---

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
HomeLabAI employs the **Acme Lab** pattern—an event-driven conversational state machine that distributes cognitive load across specialized nodes.

### 1. The Lab (Corpus Callosum)
*   **Role:** The **Translator**. It serves as the central orchestrator, converting sensory "Vibes" from the Experience layer into structured "Parameters" for the Reasoning layer, and vice-versa.
*   **Host:** Linux Coordinator Node (GPU accelerated).
*   **Core Logic:** `src/acme_lab.py`.

### 2. The Hemispheres (Nodes)
*   **🐹 Pinky (The Experience Node):**
    *   **Model:** Lightweight local LLM (e.g., Mistral/Llama-8B).
    *   **Focus:** Sensory IO, emotion detection, and real-time response.
*   **🧠 The Brain (The Reasoning Node):**
    *   **Model:** Large-scale inference engine (e.g., Llama-70B via Ollama).
    *   **Focus:** Logic, strategic planning, and long-term memory consolidation (**Dreaming**).

### 3. The Archives (Memory)
*   **Technology:** Vector database (ChromaDB) and local filesystem RAG.
*   **Role:** Managing the "Pile" (Episodic Memory) and the "Library" (Semantic Knowledge).

### 4. The Interfaces (Nerves)
How the user interacts with the Lab. All external signals are serialized through Pinky (The Secretary).

*   **🎤 The Intercom (Desktop Client):**
    *   **Role:** The primary "Hotline." A lightweight console app for high-fidelity voice and text.
    *   **Features:** Spacebar toggle for "Mute & Focus" (Type/Talk hybrid).
*   **📟 The Pager (Mobile - Planned):**
    *   **Role:** Outbound notifications ("Task Complete") sent to your phone.
*   **📝 The Fridge Note (Web - Planned):**
    *   **Role:** Passive, secure web UI for dropping links or files without waking the Brain.

---

## 🚀 Getting Started

### 1. Environment Topology
*   **Development:** WSL / Local Environment.
*   **Orchestration Node:** Remote Linux host managing STT and Pinky logic.
*   **Inference Node:** High-power GPU host (Windows/Linux) running Ollama.

### 2. Deployment & Execution
```bash
./run_remote.sh [MODE]
```
**Operation Modes:**
*   `HOSTING`: Standard production-ready operation (Persistent).
*   `MOCK_BRAIN`: Rapid testing mode that simulates the Reasoning Node.
*   `DEBUG_BRAIN`: Interactive Demo. Loads Full Stack but shuts down on disconnect.
*   **`DEBUG_PINKY`**: Local-only validation of the Experience Node logic.

### 3. Client Access
The Lab is headless. To interact, run the Intercom client on your local machine:
```bash
python src/intercom.py
```
> **⚠️ Note:** The Client version must strictly match the Server version. Mismatches will be rejected.

---

## 📚 Research & Inspiration
HomeLabAI is influenced by emerging research in agentic workflows and local model deployment:

### Voice & Mind (Hearing & Logic)
*   **[NVIDIA Nemotron-Speech-Streaming](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b):** Powering our low-latency "Hearing" layer.
*   **[Apple CLaRa](https://huggingface.co/apple/CLaRa-7B-Instruct):** Planned for the **Dreaming** phase; a RAG model designed for high-fidelity semantic compression.

### Knowledge & RAG (Memory)
*   **[sentence-transformers (MiniLM)](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2):** Our primary embedding model for local RAG.
*   **[OpenNotebook](https://github.com/lfnovo/open-notebook):** A local, private alternative to NotebookLM for research management.

---

## 🗺️ Internal Blueprint
Refer to internal documentation for technical deep-dives:

*   **[Architecture Refinement](docs/plans/Architecture_Refinement_2026.md):** The technical theory behind the Bicameral Mind.
*   **[Future Concepts (The Freezer)](docs/plans/Future_Concepts.md):** Roadmap for hardware intercoms and desktop integration.
*   **[RAG Integration Plan](docs/plans/RAG_Integration_Plan.md):** Strategy for tiered memory and long-term knowledge retention.
*   **[Agent Protocols](docs/Protocols.md):** Operational rules for development, testing, and deployment.

---

## 📜 Project History
*   **Jan 2026:** Rebranded as HomeLabAI; refined the "Bicameral Mind" (Acme Lab) architecture.
*   **Dec 2025:** Initial "Voice Gateway" prototype (Pinky & The Brain 1.0).
*   **Origins:** Originally developed as a hybrid extension for the `DeepAgent` framework.
