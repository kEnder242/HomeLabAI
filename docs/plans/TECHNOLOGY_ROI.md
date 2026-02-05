# Technology ROI & Compatibility Matrix (HomeLabAI)
**Date:** Feb 5, 2026
**Context:** Synthesis of AI research notes and hardware constraints.

## 🎯 High-Level Strategy
We prioritize optimizations that slash **P99 latency** for voice interactions and maximize **VRAM efficiency** on the Turing-based Linux node (2080 Ti).

---

## 🛠️ Optimization Matrix

| Technology | Target Node | ROI | Complexity | Compatibility / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **NVIDIA MPS** | Linux (2080 Ti) | **High** | Low | Allows Pinky (Mistral) and Brain (Llama) to share 11GB VRAM with zero context-switch overhead. |
| **Liger-Kernel** | Linux (2080 Ti) | **Critical**| Med | Reduces peak VRAM by ~80%. Unblocks 14B models for Pinky. Requires `torch.compile`. |
| **vLLM Serving** | Linux (Coordinator)| **Extreme** | High | Replaces Ollama for the Web Intercom. SOTA throughput. Possible conflict with NeMo EarNode. |
| **MAXS Reasoning**| Windows (4090) | **Med** | High | Meta-Adaptive Exploration. Logic for "lookahead" before tool calls. Best for deep-think tasks. |
| **Voxtral (STT)** | Browser / Linux | **High** | Med | Mistral's sonic-speed transcription. Backup for NeMo if EarNode latency spikes. |

---

## 🏗️ Hardware Allocation (Bicameral Model)

### 🐹 Node: Pinky (Linux / 2080 Ti)
*   **Role:** Sensory I/O, Tool Execution, Fast Reflexes.
*   **Constraint:** 11GB VRAM.
*   **Optimization Path:** MPS + Liger-Kernel. Keep models < 8B unless using Fused Kernels.

### 🧠 Node: The Brain (Windows / 4090)
*   **Role:** Strategic Planning, Complex Reasoning, Memory Consolidation.
*   **Constraint:** No native Triton (stable). 
*   **Optimization Path:** WSL2 for Triton support OR `triton-windows` experimental wheels. Use for 70B+ models.

---

## 🔮 The "Long Haul" Roadmap

### Phase 1: Stability (Active)
- [x] **RAG Context Bridge:** Fixed hallucination by forwarding Archive snippets to Brain.
- [ ] **NVIDIA MPS Setup:** Enable daemon on Linux to reduce "Nervous Tic" jitters.

### Phase 2: Scale (Next Up)
- [ ] **Liger-Kernel Integration:** Apply fused kernels to Pinky's local model loader.
- [ ] **Web Intercom (Text):** Establish WebSocket baseline in `Portfolio_Dev`.

### Phase 3: Speed (The Vision)
- [ ] **vLLM Transition:** Migrate coordinator inference from Ollama to vLLM.
- [ ] **Web Intercom (Voice):** MediaStream API PCM streaming.

---
## 🏁 Immediate Next Actions (Unblocking)

1.  **Verify RAG:** Run a query like "Tell me about my 2022 PECI stress test paper" and confirm the Brain uses the PDF context.
2.  **Enable MPS:** Run `nvidia-cuda-mps-control -d` on Linux to start the multi-process daemon.
3.  **Web Intercom:** Begin `Portfolio_Dev/field_notes/intercom.html` scaffolding.

---
*BKM: Archive research URLs in Keep once incorporated into this roadmap to prevent "Note Bloat".*
