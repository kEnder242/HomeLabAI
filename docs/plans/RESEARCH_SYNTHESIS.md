# RESEARCH_SYNTHESIS.md: Cohesive Implementation Roadmap (v2.0)
**Date:** Feb 6, 2026
**Status:** DRAFT (Synthesis of Keep Research & Current Session Insights)

## 🔭 The Unified Vision
To bridge the "Bicameral" hardware (Pinky 2080 Ti & Brain 4090 Ti) using a **Persistent Memory-First** architecture. We treat the local file system as an external "Long-Term Memory" and use Test-Time Reasoning to maximize the output quality of small local models (Mistral-7B).

---

## 🔬 Implementation Mapping: Paper-to-Code

| Research Anchor | Core Architecture | Role in `ai_engine.py` / HomeLabAI |
| :--- | :--- | :--- |
| **FS-Researcher** (2602.01566) | Dual-Agent: Context Builder + Report Writer | **Foundation:** `nibble.py` is the Context Builder. The Web Intercom is the Report Writer. Use FS as durable external memory. |
| **WideSeek-R1** | Width Scaling: Parallel subagent orchestration. | **Orchestration:** Pinky delegates subtasks (e.g., "Extract dates", "Summarize tech") to parallel subagent contexts to improve Item F1 score. |
| **TTCS** (2601.22628) | Test-Time Curriculum: Synthesizer + Solver. | **Quality:** Before writing a log, Pinky must synthesize 3 hard questions about the text and solve them (Self-Evolution). |
| **Agentic-R** | Learning to Retrieve: Utility-based ranking. | **Memory Bridge:** Re-rank historical JSON context based on its utility to the *final answer*, not just text similarity. |
| **Apple CLaRa** | Semantic Compression: 16x-128x density. | **Optimization:** Compress raw monthly logs into high-density "Technical Abstracts" before ingestion by The Brain. |
| **MiMo-V2-Flash** | Multi-Objective RL: Post-execution feedback. | **Observability:** Use Grafana/Prometheus feedback to "reward" the agent's visualization scripts (RL-Text2Vis). |
| **RLM** (Recursive LMs) | Context as a Code-Readable String. | **Pattern:** Implement `peek_related_notes()` allowing Pinky to read the FS like a string via tools. |

---

## 📊 Research Impact Reality Check (v2.0)

| Paper | Project Impact | "Same Idea" vs. "Game Changer" | % Architectural Change |
| :--- | :--- | :--- | :--- |
| **FS-Researcher** | **Static Synthesis Core.** We transitioned from stateless LLM calls to a durable, hierarchical file-system memory. | **Game Changer.** This redefined how Pinky "remembers." It moved the burden from the model's context to the project's disk. | **90%** |
| **TTCS** | **The Reasoning Loop.** Introduced the "Synthesize-then-Solve" pattern in `ai_engine_v2.py`. | **Evolutionary.** It forced the model to think before writing, which caught the "PECI/Simics" era errors but introduced "filler" risks. | **60%** |
| **Apple CLaRa** | **Semantic Compression.** Implemented as the `SemanticCondenser` to handle large raw log backlogs. | **Useful Idea.** It’s a specialized prompt wrapper that keeps our reasoning loop efficient, but doesn't fundamentally change the data flow. | **40%** |
| **Agentic-R** | **Memory Utility.** Currently used for injecting historical context (e.g., previous month's JSON). | **Seed Idea.** It's currently "Just an idea that seems the same." We haven't fully implemented the utility-based re-ranking yet. | **70%** |
| **Liger-Kernel** | **VRAM Optimization.** Pending installation and bench-test on Pinky-Node (2080 Ti). | **Efficiency Target.** Aims for 80%+ VRAM reduction to fit 14B models on 11GB. | **0% (Pending)** |

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

## 📝 Stale Content Strategy: `Research_and_Inspiration.md`
To prevent the "Goldmine" from becoming "Sludge":
1. **Archive the Stale:** Move items older than 3 months to `docs/archive/RESEARCH_RETIRED.md`.
2. **Breadcrumb the Active:** The `Research_and_Inspiration.md` should now serve ONLY as a staging area for new links. Once a paper is mapped in this `RESEARCH_SYNTHESIS.md`, it is archived from the list.
3. **Agent Breadcrumbs:** Every AI response regarding research will now point to this file: `[Ref: docs/plans/RESEARCH_SYNTHESIS.md]`.

---
*Next Action: Implement the TTCS "Synthesize-then-Solve" loop in ai_engine_v2.py.*
