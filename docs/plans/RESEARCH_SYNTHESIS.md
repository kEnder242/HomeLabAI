# RESEARCH_SYNTHESIS.md: Cohesive Implementation Roadmap (v2.2)
**Date:** May 20, 2026
**Status:** DRAFT (Standardized Unified Schema with Git Links)

## Telescope The Unified Vision
To bridge the "Bicameral" hardware (Pinky 2080 Ti & Brain 4090 Ti) using a **Persistent Memory-First** architecture. We treat the local file system as an external "Long-Term Memory" and use Test-Time Reasoning to maximize the output quality of small local models (Llama-3.2-3B).

---

## 🔬 Implementation Mapping: Paper-to-Code

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Git Link | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FS-Researcher** | 2602.01566 | Dual-Agent: Context Builder + Report Writer | **Foundation:** `nibble.py` is the Context Builder [FEAT-095]. | [field_notes/nibble.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/nibble.py) | **100%** |
| **Agentic-R** | 2601.11888 | Learning to Retrieve: Utility-based ranking. | **Memory Bridge:** `ArchiveMemory` utility ranking [FEAT-080]. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **85%** |
| **TTCS** | 2601.22628 | Test-Time Curriculum: Synthesizer + Solver. | **Quality:** Mitigates repetition loops via Synthesize-then-Solve patterns [FEAT-114]. | [field_notes/ai_engine_v2.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/ai_engine_v2.py) | **100%** |
| **Apple CLaRa** | 2511.18659 | Semantic Compression: 16x-128x density. | **Optimization:** `SemanticCondenser` compresses raw logs [FEAT-073]. | [field_notes/ai_engine_v2.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/ai_engine_v2.py) | **100%** |
| **Liger Kernel** | 2410.10989 | Efficient Triton Kernels for LLM Training. | **Efficiency:** Maximizing 8B residency on 11GB silicon [FEAT-031]. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **100%** |
| **RLM** | N/A | Context as a Code-Readable String. | **Discovery:** `peek_related_notes()` logic [FEAT-117]. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **100%** |
| **TTT-Discover** | 2601.16175 | Test-Time Discovery: RL-based optimization. | **Automation:** Planned: RL loops for bug reproduction. | N/A | **0%** |
| **WideSeek-R1** | N/A | Width Scaling: Parallel subagent orchestration. | **Orchestration:** Planned: Parallel contexts for extraction. | N/A | **0%** |
| **MiMo-V2-Flash** | N/A | Multi-Objective RL: Post-execution feedback. | **Observability:** Planned: Use Grafana feedback to reward agents. | N/A | **0%** |
| **Dreaming** | 2603.04257 | Subconscious Compression (Memex). | **Consolidation:** `dream_cycle.py` moving logs to Wisdom [FEAT-067]. | [dream_cycle.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/dream_cycle.py) | **100%** |
| **Internal Debate** | 2603.00142 | Moderated Consensus (Byzantine ToM). | **Consensus:** `delegate_internal_debate` facilitates reasoning [FEAT-071]. | [logic/cognitive_hub.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py) | **100%** |
| **AT2QA** | 2603.01853 | Autonomous Exploration Pivot. | **Autonomy:** [FEAT-173] Pivot-query logic pass for thin results. | [logic/cognitive_hub.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py) | **Design** |
| **Agentic FS** | 2602.20478 | Context as a File System. | **Grounding:** Validates our "Static Synthesis" architecture. | [field_notes/mass_scan.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py) | **100%** |
| **13-Param Reason** | 2602.04118 | Extreme parameter efficiency. | **Sentinel:** Optimization logic for 1B "Sentinel" mice nodes. | [nodes/lab_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/lab_node.py) | **Active** |
| **REDSearcher** | 2602.14234 | Long-Horizon Search Scaling. | **Discovery:** framework for deep technical history discovery. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **Design** |
| **VibeThinker-3B** | 2606.16140 | Verifiable Reasoning / Spectrum-to-Signal. | **Sanity:** Unified local base model for Phase 10 [FEAT-368]. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Active** |
| **MCompassRAG** | 2606.18508 | Metadata as semantic compass. | **Discovery:** Planned: Metadata-guided paragraph RAG. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **Design** |

---

## 📇 Retired & Defeatured Research

These papers or concepts were evaluated and decommissioned during our architectural refinement to prevent technical clutter:

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Git Link / Reason | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Banter Decay** | N/A | Frequency-based idling. | Replaced by [FEAT-152] Metabolism of Presence [FEAT-039]. | Replaced by passive wakefulness logic. | **DEFEATURED** |
| **Persona-Locked Dispatch** | N/A | Rigid isolation. | Rigid isolation prevented collaborative synthesis [FEAT-068]. | Bleed prevention replaced by shared Identity Bedrock. | **DEFEATURED** |

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

| Research Anchor | ArXiv ID | Strategy | Git Link / Implementation | Status |
| :--- | :--- | :--- | :--- | :--- |
| **MAXS** | 2601.12538 | Lookahead hooks to estimate "Value of Information" before tool calls. | [logic/cognitive_hub.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py) | **Planned** |
| **Voxtral** | N/A | Transition from NeMo EarNode to native high-speed Mistral STT. | N/A | **Planned** |
| **vLLM Serving** | N/A | Achieved SOTA serving throughput for the Web Intercom. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **100%** |
| **3x3 CVT** | N/A | High-Density Resume Indexer. Correlates Focal goals with Artifact evidence. | [field_notes/ai_engine_v2.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/ai_engine_v2.py) | **100%** |
| **Agentic-R** | 2601.11888 | Implement in ArchiveMemory for deep technical search. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **Active** |
| **KV‑Cache Routing** | 2606.32032 | Adaptive cache sharing across persona swaps. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Planned** |
| **Oracle GraphRAG** | N/A | Graph‑based retrieval for structured artifacts. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **Planned** |
| **DSpark Speculative Decoding** | N/A | Faster per‑token generation for role‑token switches. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Planned** |
| **Semantic Compass (MCompassRAG)** | 2606.26300 | Metadata‑driven semantic navigation of the archive. | [nodes/archive_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py) | **Planned** |

---

## 📝 Stale Content Strategy: `Research_and_Inspiration.md`
To prevent the "Goldmine" from becoming "Sludge":
1. **Archive the Stale:** Move items older than 3 months to `docs/archive/RESEARCH_RETIRED.md`.
2. **Breadcrumb the Active:** The `Research_and_Inspiration.md` should now serve ONLY as a staging area for new links. Once a paper is mapped in this `RESEARCH_SYNTHESIS.md`, it is archived from the list.
3. **Agent Breadcrumbs:** Every AI response regarding research will now point to this file: `[Ref: docs/plans/RESEARCH_SYNTHESIS.md]`.

---

## 🌌 EPOCH 2: THE COGNITIVE EXPANSION & LOST GEMS PINNING (May 20, 2026)
*Source: Google Keep Brain Dump (Notes Archive) & Git Commit History Audit (Commit 34a3bd5)*

### 💎 THE GEMS: GAME CHANGERS
*High-impact research that aligns with our Multi-LoRA / 11GB silicon strategy.*

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Git Link | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Thinking to Recall** | 2603.09906 | Uses CoT as a "computational buffer" for factual priming. | Implemented via [FEAT-114] TTCS logic. | [field_notes/ai_engine_v2.py](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/ai_engine_v2.py) | **100%** |
| **AutoHarness** | 2603.03329 | Synthesizing Python guardrails for agent self-verification. | Grounds future [FEAT-353] Verifier Synthesis. | N/A | **Planned** |
| **Stochastic KV Routing** | 2604.22782 | Adaptive depth-wise cache sharing (Apple MLR). | Optimization pattern for [FEAT-031] Liger. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Active** |
| **ARIS** | 2605.03042 | Adversarial multi-agent collaboration for research. | Theoretical base for [FEAT-071] Internal Debate. | [logic/cognitive_hub.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py) | **100%** |
| **CodeTracer** | 2604.11641 | Traceable agent states & failure onset localization. | Enhanced [FEAT-151] Forensic Ledger visibility. | [debug/test_forensic_logging.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_forensic_logging.py) | **100%** |
| **PersonaVLM** | 2604.13074 | Proactive memory extraction & response alignment. | Core logic for [FEAT-067] Subconscious Dreaming. | [dream_cycle.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/dream_cycle.py) | **100%** |
| **TriAttention** | 2604.04921 | Trigonometric KV compression (10x reduction). | Future optimization for [FEAT-031] VRAM efficiency. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Active** |
| **Bonsai-ML** | N/A | High-fidelity fine-tuning for structured reasoning. | Grounds the [FEAT-352] Qwen Pivot strategy. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Active** |
| **BKM-015: Bedrock** | N/A | Prefix-cache stability through shared identity strings. | Shared IDENTITY_BEDROCK implementation. | [nodes/loader.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py) | **Live** |
| **Stoic Strategist** | N/A | Filler stripping ("Certainly!", etc.) & strategic focus. | [FEAT-023] Persona constraint enforcement. | [debug/test_persona_bugs.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_persona_bugs.py) | **Live** |
| **VRAM Guard** | N/A | Deep Sleep failover on silicon exhaustion. | [FEAT-036] Attendant VRAM characterization. | [debug/test_vram_guard.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_vram_guard.py) | **Live** |
| **Hierarchical Mind** | N/A | Specialized Architect node for BKM generation. | [FEAT-037] Semantic map generation. | [debug/test_architect_flow.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_architect_flow.py) | **Live** |
| **Nightly Recruiter** | N/A | Automated resume mapping to active job listings. | [FEAT-038] Recruiter query matching. | [debug/test_recruiter.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_recruiter.py) | **Live** |
| **Strategic Amygdala** | N/A | Input sentinels gating voice/typing console modes. | [FEAT-032] console barge-in sentinels. | [debug/mic_toggle_audit.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/mic_toggle_audit.py) | **Live** |
| **Iron Moat** | N/A | Prevent persona bleed / clear visual panels on hello. | [FEAT-033] Persona Isolation boundaries. | [debug/test_persona_logic.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_persona_logic.py) | **Live** |
| **Barge-In interrupts** | N/A | Cancel long execution steps via voice/hotkey patterns. | [FEAT-034] ear_poller stream cancellation. | [debug/test_barge_in_logic.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_barge_in_logic.py) | **Live** |
| **Zombie Port Recovery** | N/A | Monitor WS socket status & restore engine on lockups. | [FEAT-035] Foyer port watchdog. | [debug/test_zombie_recovery.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_zombie_recovery.py) | **Live** |
