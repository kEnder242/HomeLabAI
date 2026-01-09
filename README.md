# Acme Lab: Voice-Activated Personal Knowledge Assistant

**Acme Lab** is a hybrid AI orchestrator inspired by "Pinky and the Brain." It models a **Bicameral Mind** using distributed hardware.

## 🔭 High-Level Vision
We believe the future of personal AI is a synthesis of two distinct cognitive styles:
*   **The Right Hemisphere (Pinky):** Intuitive, Emotional, Aware. He manages the "Vibe," the connection to reality, and the user interface.
*   **The Left Hemisphere (The Brain):** Logical, Abstract, Precise. He manages the "Truth," the planning, and the deep reasoning.

### The "Talk & Read" Philosophy
*   **Voice Input:** Because speaking is faster than typing.
*   **Text Output:** Because reading is faster than listening.
*   **The Loop:** A tight, low-latency feedback loop designed for "Vibe Coding" and brainstorming.

---

## 🏗️ Architecture: The Bicameral Mesh

The system is an **Event-Driven Conversational State Machine**.

### 1. The Lab (Corpus Callosum)
*   **Host:** `z87-Linux` (NVIDIA 2080 Ti).
*   **File:** `src/acme_lab.py`.
*   **Role:** The **Translator**. It converts Pinky's "Vibes" into The Brain's "Parameters" and The Brain's "Logic" into Pinky's "Actions."

### 2. The Hemispheres (Nodes)
*   **🐹 Pinky (Right Brain):**
    *   **Model:** `mistral:7b` (Local).
    *   **Role:** The Experience Engine. Handling Sensory IO, Emotion, and Presence.
    *   **Tools:** `delegate_to_brain`, `critique_brain`, `reply_to_user`.
*   **🧠 The Brain (Left Brain):**
    *   **Model:** `llama3:70b` (Remote Windows GPU via Ollama).
    *   **Role:** The Reasoning Engine. Handling Logic, Code, and Memory Consolidation ("Dreaming").

### 3. The Archives (Memory)
*   **Tech:** ChromaDB.
*   **Role:** The "Pile" (Episodic Memory) and the "Library" (Semantic Memory).

---

## 🚀 Getting Started

### 1. Environment Orientation
*   **Dev Machine:** WSL (`~/HomeLabAI`).
*   **Target Host:** `z87-Linux.local` (`~/AcmeLab`).

### 2. Deployment
Use the helper script to sync and run remotely:
```bash
./run_remote.sh [MODE]
```
**Modes:**
*   `SERVICE`: Standard operation.
*   `MOCK_BRAIN`: Fast logic testing (simulates Brain responses).
*   `DEBUG_PINKY`: Local logic only.

### 3. Key Commands
*   **`src/test_round_table.py`**: Validate the logic loop (Fast).
*   **`src/mic_test.py`**: Interactive Voice Client.

---

## 📚 Research & Inspiration

A collection of papers and projects influencing our design.

*   **[NVIDIA Nemotron-Speech-Streaming](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b):** Powering our low-latency "Hearing" layer.
*   **[Recursive Language Models (RLMs)](https://www.marktechpost.com/2026/01/02/recursive-language-models-rlms-from-mits-blueprint-to-prime-intellects-rlmenv-for-long-horizon-llm-agents/?amp):** Inspiration for our "Pinky Reads Tools" approach.
*   **[Local Multi-Agent Orchestration](https://www.marktechpost.com/2025/12/05/how-to-design-a-fully-local-multi-agent-orchestration-system-using-tinyllama-for-intelligent-task-decomposition-and-autonomous-collaboration/?amp):** Validates the Small (Pinky) -> Large (Brain) routing strategy.

---

## 📜 Project History
*   **Jan 2026:** Refined into "Bicameral Mind" architecture (Right/Left Brain).
*   **Dec 2025:** Initial "Voice Gateway" prototype (Pinky & The Brain 1.0).
*   **Origins:** Forked from `DeepAgent`.