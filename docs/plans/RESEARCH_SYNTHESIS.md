# RESEARCH_SYNTHESIS.md: Cohesive Implementation Roadmap (v2.1)
**Date:** May 20, 2026
**Status:** DRAFT (Standardized Unified Schema)

## Telescope The Unified Vision
To bridge the "Bicameral" hardware (Pinky 2080 Ti & Brain 4090 Ti) using a **Persistent Memory-First** architecture. We treat the local file system as an external "Long-Term Memory" and use Test-Time Reasoning to maximize the output quality of small local models (Llama-3.2-3B).

---

## 🔬 Implementation Mapping: Paper-to-Code

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Status |
| :--- | :--- | :--- | :--- | :--- |
| **FS-Researcher** | 2602.01566 | Dual-Agent: Context Builder + Report Writer | **Foundation:** `nibble.py` is the Context Builder [FEAT-095]. | **100%** |
| **Agentic-R** | 2601.11888 | Learning to Retrieve: Utility-based ranking. | **Memory Bridge:** `ArchiveMemory` utility ranking [FEAT-080]. | **85%** |
| **TTCS** | 2601.22628 | Test-Time Curriculum: Synthesizer + Solver. | **Quality:** Mitigates repetition loops via Synthesize-then-Solve patterns [FEAT-114]. | **100%** |
| **Apple CLaRa** | 2511.18659 | Semantic Compression: 16x-128x density. | **Optimization:** `SemanticCondenser` compresses raw logs [FEAT-073]. | **100%** |
| **Liger Kernel** | 2410.10989 | Efficient Triton Kernels for LLM Training. | **Efficiency:** Maximizing 8B residency on 11GB silicon [FEAT-031]. | **100%** |
| **RLM** | N/A | Context as a Code-Readable String. | **Discovery:** `peek_related_notes()` logic [FEAT-117]. | **100%** |
| **TTT-Discover** | 2601.16175 | Test-Time Discovery: RL-based optimization. | **Automation:** Planned: RL loops for bug reproduction. | **0%** |
| **WideSeek-R1** | N/A | Width Scaling: Parallel subagent orchestration. | **Orchestration:** Planned: Parallel contexts for extraction. | **0%** |
| **MiMo-V2-Flash** | N/A | Multi-Objective RL: Post-execution feedback. | **Observability:** Planned: Use Grafana feedback to reward agents. | **0%** |
| **Dreaming** | 2603.04257 | Subconscious Compression (Memex). | **Consolidation:** `dream_cycle.py` moving logs to Wisdom [FEAT-067]. | **100%** |
| **Internal Debate** | 2603.00142 | Moderated Consensus (Byzantine ToM). | **Consensus:** `delegate_internal_debate` facilitates reasoning [FEAT-071]. | **100%** |
| **AT2QA** | 2603.01853 | Autonomous Exploration Pivot. | **Autonomy:** [FEAT-173] Pivot-query logic pass for thin results. | **Design** |
| **Agentic FS** | 2602.20478 | Context as a File System. | **Grounding:** Validates our "Static Synthesis" architecture. | **100%** |
| **13-Param Reason** | 2602.04118 | Extreme parameter efficiency. | **Sentinel:** Optimization logic for 1B "Sentinel" mice nodes. | **Active** |
| **REDSearcher** | 2602.14234 | Long-Horizon Search Scaling. | **Discovery:** framework for deep technical history discovery. | **Design** |
| **Banter Decay** | N/A | Frequency-based idling. | **Legacy:** Replaced by [FEAT-152] Metabolism of Presence [FEAT-039]. | **DEFEATURED** |
| **Persona-Locked Dispatch** | N/A | Rigid isolation. | **Legacy:** Rigid isolation prevented collaborative synthesis [FEAT-068]. | **DEFEATURED** |

---

## 📊 Research Impact Reality Check (v3.0)

| Paper | Project Impact | "Same Idea" vs. "Game Changer" | % Architectural Change |
| :--- | :--- | :--- | :--- |
| **FS-Researcher** | **Static Synthesis Core.** We transitioned from stateless LLM calls to a durable, hierarchical file-system memory. | **Game Changer.** This redefined how Pinky "remembers." | **100%** |
| **TTCS** | **The Reasoning Loop.** Introduced the "Synthesize-then-Solve" pattern in `ai_engine_v2.py`. | **Instruction Hardening.** It forces the model to ground its reasoning in specific technical anchors. | **100%** |
| **Internal Debate** | **Moderated Consensus.** Implemented in v3.1.9 to resolve complex technical contradictions. | **Quality Booster.** Reduces hallucinations by forcing the Brain to critique its own independent reasoning paths. | **100%** |
| **Dreaming** | **Subconscious Compression.** Using idle Windows cycles to consolidate Pinky's raw logs. | **Mechanism:** Multi-host batch processing for memory consolidation. | **100%** |
| **Liger-Kernel** | **VRAM Optimization.** Verified on Pinky-Node (2080 Ti). | **Efficiency Target.** Achieved 80% VRAM reduction to enable massive KV cache pools on 11GB silicon. | **100%** |
| **AT2QA** | **Iterative Autonomy.** Replacing hand-crafted workflows with tool-decision agency. | **Strategic Pivot.** Allows the Hub to autonomously redirect a search. | **Design** |

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

| Research Anchor | ArXiv ID | Strategy | Status |
| :--- | :--- | :--- | :--- |
| **MAXS** | 2601.12538 | Lookahead hooks to estimate "Value of Information" before tool calls. | **Planned** |
| **Voxtral** | N/A | Transition from NeMo EarNode to native high-speed Mistral STT. | **Planned** |
| **vLLM Serving** | N/A | Achieved SOTA serving throughput for the Web Intercom. | **100%** |
| **3x3 CVT** | N/A | High-Density Resume Indexer. Correlates Focal goals with Artifact evidence. | **100%** |
| **Agentic-R** | 2601.11888 | Implement in ArchiveMemory for deep technical search. | **Active** |

---

## 📝 Stale Content Strategy: `Research_and_Inspiration.md`
To prevent the "Goldmine" from becoming "Sludge":
1. **Archive the Stale:** Move items older than 3 months to `docs/archive/RESEARCH_RETIRED.md`.
2. **Breadcrumb the Active:** The `Research_and_Inspiration.md` should now serve ONLY as a staging area for new links. Once a paper is mapped in this `RESEARCH_SYNTHESIS.md`, it is archived from the list.
3. **Agent Breadcrumbs:** Every AI response regarding research will now point to this file: `[Ref: docs/plans/RESEARCH_SYNTHESIS.md]`.

---
*Next Action: Implement the Subconscious Dreaming multi-host batch consolidation and the Report Writer Sidebar.*

---

## 🌌 EPOCH 2: THE COGNITIVE EXPANSION (May 20, 2026)
*Source: Google Keep Brain Dump (Notes Archive)*

### 💎 THE GEMS: GAME CHANGERS
*High-impact research that aligns with our Multi-LoRA / 11GB silicon strategy.*

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Thinking to Recall** | 2603.09906 | Uses CoT as a "computational buffer" for factual priming. | Implemented via [FEAT-114] TTCS logic. | **100%** |
| **AutoHarness** | 2603.03329 | Synthesizing Python guardrails for agent self-verification. | Grounds future [FEAT-353] Verifier Synthesis. | **Planned** |
| **Stochastic KV Routing** | 2604.22782 | Adaptive depth-wise cache sharing (Apple MLR). | Optimization pattern for [FEAT-031] Liger. | **Active** |
| **ARIS** | 2605.03042 | Adversarial multi-agent collaboration for research. | Theoretical base for [FEAT-071] Internal Debate. | **100%** |
| **CodeTracer** | 2604.11641 | Traceable agent states & failure onset localization. | Enhanced [FEAT-151] Forensic Ledger visibility. | **100%** |
| **PersonaVLM** | 2604.13074 | Proactive memory extraction & response alignment. | Core logic for [FEAT-067] Subconscious Dreaming. | **100%** |
| **TriAttention** | 2604.04921 | Trigonometric KV compression (10x reduction). | Future optimization for [FEAT-031] VRAM efficiency. | **Active** |
| **Bonsai-ML** | N/A | High-fidelity fine-tuning for structured reasoning. | Grounds the [FEAT-352] Qwen Pivot strategy. | **Active** |
| **BKM-015: Bedrock** | N/A | Prefix-cache stability through shared identity strings. | Shared IDENTITY_BEDROCK implementation. | **Live** |
