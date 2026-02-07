# AI Master Plan: The Long Haul (2026)
**Date:** Feb 5, 2026
**Status:** DRAFT (Synthesized from Google Keep Research)

## 🔭 The Vision
To transform the Acme Lab into a high-throughput, low-latency agentic ecosystem that seamlessly bridges the "Bicameral" hardware (Linux 2080 Ti & Windows 4090 Ti).

---

## 🛠️ Optimization Roadmap (High ROI)

### Phase 1: High-Efficiency Inference (VRAM & Throughput)
*   **Liger-Kernel:** Integrate fused kernels into the Linux node model loader. 
    *   *Goal:* Reduce peak VRAM by 84% to fit 14B+ models on 11GB.
*   **vLLM:** Transition the web coordinator from Ollama to vLLM.
    *   *Goal:* Achieve SOTA serving throughput for the Web Intercom.
*   **NVIDIA MPS:** Establish persistent daemon for GPU multi-tenancy.
    *   *Status:* **ACTIVE.** Successfully running concurrent nodes.

### Phase 2: Advanced Reasoning (Agentic Loops)
*   **MAXS (Meta-Adaptive Exploration):** Implement "lookahead" hooks in `agent_executor.py`.
    *   *Goal:* Estimate the "Value of Information" before calling expensive Brain tools.
*   **Internal Debate:** Refactor Pinky to facilitate internal debate between Brain nodes.
    *   *Goal:* Improve accuracy on complex reasoning tasks (arXiv:2601.12538).

### Phase 3: Voice Mastery (Sonic STT/TTS)
*   **Voxtral:** Benchmark Mistral's sonic-speed transcription against current NeMo EarNode.
*   **PersonaPlex:** Explore Nvidia's open model for simultaneous listen/talk voice interaction.

---

## 🔬 Key Research Anchors
1.  **WideSeek-R1:** Scaling width for broad information seeking.
2.  **Agentic-R:** Learning to retrieve for agentic search (RAG improvement).
3.  **MiMo-V2-Flash:** Multi-Objective Reinforcement Learning for text-to-visualization.
4.  **TTCS (arXiv:2601.22628):** Test-Time Curriculum Synthesis for self-evolving reasoning loops.
5.  **FS-Researcher (arXiv:2602.01566):** Dual-agent frameworks using file-systems for long-horizon memory scaling.

---

## 🎯 Targeted Resume Builder (CVE Format)
*   **Goal:** Re-index notes from 2005–2024 using the "3x3 CVT" format.
*   **Logic:** Bucket performance review insights, correlate with 3 relevant technical notes per year.
*   **Strategy:** Highlight "Point of Failure" documentation (BKM Protocol) as a core competency.

---
*Next Action: Implement Liger-Kernel bench-test on Pinky-Node.*
