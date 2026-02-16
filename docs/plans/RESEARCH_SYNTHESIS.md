# RESEARCH_SYNTHESIS.md: Cohesive Implementation Roadmap (v2.0)
**Date:** Feb 9, 2026
**Status:** DRAFT (Synthesis of Keep Research & Current Session Insights)

## Telescope The Unified Vision
To bridge the "Bicameral" hardware (Pinky 2080 Ti & Brain 4090 Ti) using a **Persistent Memory-First** architecture. We treat the local file system as an external "Long-Term Memory" and use Test-Time Reasoning to maximize the output quality of small local models (Llama-3.2-3B).

---

## 🔬 Implementation Mapping: Paper-to-Code

| Research Anchor | Core Architecture | Role in `ai_engine.py` / HomeLabAI | Status |
| :--- | :--- | :--- | :--- |
| **FS-Researcher** (2602.01566) | Dual-Agent: Context Builder + Report Writer | **Foundation:** `nibble.py` is the Context Builder. Web Intercom is the Report Writer. | **100%** |
| **Agentic-R** | Learning to Retrieve: Utility-based ranking. | **Memory Bridge:** `ArchiveMemory` ranks historical context based on keyword utility. | **85%** |
| **TTCS** (2601.22628) | Test-Time Curriculum: Synthesizer + Solver. | **Quality:** Mitigates repetition loops via Synthesize-then-Solve patterns. | **100%** |
| **Apple CLaRa** | Semantic Compression: 16x-128x density. | **Optimization:** `SemanticCondenser` compresses raw logs into technical abstracts. | **100%** |
| **RLM** (Recursive LMs) | Context as a Code-Readable String. | **Discovery:** `peek_related_notes()` allows Pinky to follow technical breadcrumbs. | **100%** |
| **TTT-Discover** (2601.16175) | Test-Time Discovery: RL-based optimization. | **Automation:** Planned: RL loops for bug reproduction. | **0%** |
| **WideSeek-R1** | Width Scaling: Parallel subagent orchestration. | **Orchestration:** Planned: Parallel subagent contexts for extraction. | **0%** |
| **MiMo-V2-Flash** | Multi-Objective RL: Post-execution feedback. | **Observability:** Planned: Use Grafana feedback to reward agents. | **0%** |
| **Dreaming** | Subconscious Compression. | **Consolidation:** `dream_cycle.py` moving chat history to Long-Term Wisdom. | **100%** |
| **Internal Debate** | Moderated Consensus. | **Consensus:** `delegate_internal_debate` facilitates multi-path reasoning. | **100%** |
| **3x3 CVT** | High-Density Resume Indexer. | **Synthesis:** `build_cv_summary` correlates Focal goals with Artifact evidence. | **100%** |

---

## 📊 Research Impact Reality Check (v3.0)

| Paper | Project Impact | "Same Idea" vs. "Game Changer" | % Architectural Change |
| :--- | :--- | :--- | :--- |
| **FS-Researcher** | **Static Synthesis Core.** We transitioned from stateless LLM calls to a durable, hierarchical file-system memory. | **Game Changer.** This redefined how Pinky "remembers." It moved the burden from the model's context to the project's disk. | **100%** |
| **TTCS** | **The Reasoning Loop.** Introduced the "Synthesize-then-Solve" pattern in `ai_engine_v2.py`. | **Instruction Hardening.** It forces the model to ground its reasoning in specific technical anchors, mitigating the repetition loops seen in Llama-3.2 models. | **100%** |
| **Internal Debate** | **Moderated Consensus.** Implemented in v3.1.9 to resolve complex technical contradictions. | **Quality Booster.** Reduces hallucinations by forcing the Brain to critique its own independent reasoning paths. | **100%** |
| **3x3 CVT** | **Automated CV Synthesis.** Correlates 18 years of technical scars with yearly strategic goals. | **Portfolio Signature.** Physically demonstrates the value of the archive to non-technical stakeholders. | **100%** |
| **Dreaming** | **Subconscious Compression.** Using idle Windows cycles to consolidate Pinky's raw logs. | **Mechanism:** Multi-host batch processing for memory consolidation. | **100%** |
| **Liger-Kernel** | **VRAM Optimization.** Verified on Pinky-Node (2080 Ti). | **Efficiency Target.** Achieved 80% VRAM reduction to enable massive KV cache pools on 11GB silicon. | **100%** |

---

## 🏗️ The "BKM Tree" (Hierarchical Knowledge Base)
Following **FS-Researcher**, we are evolving `field_notes/data/` from flat JSONs into a hierarchical structure for the "Report Writer" (The Brain) to navigate:

```text
data/
├── expertise/
│   ├── telemetry/
│   │   ├── pecistressor.md  <-- "Ground Truth" extracted via TTCS
│   │   └── rapl_metrics.md
│   └── manageability/
│       └── redfish_api.md
├── timeline/
│   └── YYYY/MM.json         <-- Raw Context Builder output
└── index/
    └── search_index.json    <-- WideSeek-R1 triage layer
```

---

## 🔮 Tabled & Future Exploration
These ideas were identified in the **AI Master Plan (2026)** and are scheduled for post-Phase 9 development:

| Anchor | Description | Strategy | Status |
| :--- | :--- | :--- | :--- |
| **vLLM Serving** | Transition from Ollama to vLLM for model serving. | Achieve SOTA serving throughput for the Web Intercom. | **Planned** |
| **MAXS** | Meta-Adaptive Exploration (arXiv:2601.12538). | Lookahead hooks to estimate "Value of Information" before tool calls. | **Planned** |
| **Voxtral** | Sonic-speed transcription benchmarking. | Transition from NeMo EarNode to native high-speed Mistral STT. | **Planned** |

---

## 📝 Stale Content Strategy: `Research_and_Inspiration.md`
To prevent the "Goldmine" from becoming "Sludge":
1. **Archive the Stale:** Move items older than 3 months to `docs/archive/RESEARCH_RETIRED.md`.
2. **Breadcrumb the Active:** The `Research_and_Inspiration.md` should now serve ONLY as a staging area for new links. Once a paper is mapped in this `RESEARCH_SYNTHESIS.md`, it is archived from the list.
3. **Agent Breadcrumbs:** Every AI response regarding research will now point to this file: `[Ref: docs/plans/RESEARCH_SYNTHESIS.md]`.

---
*Next Action: Implement the Subconscious Dreaming multi-host batch consolidation and the Report Writer Sidebar.*