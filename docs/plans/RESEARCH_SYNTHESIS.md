# Research Synthesis: Implementation Roadmap
**Date:** May 20, 2026
**Status:** DRAFT (Standardized Unified Schema with Git Links)

## Telescope The Unified Vision
To integrate local (2080 Ti) and remote (4090 Ti) hardware using a memory-first architecture. We treat the local file system as an external "Long-Term Memory" and use Test-Time Reasoning to maximize the output quality of small local models (Llama-3.2-3B).

---

## 🔬 Implementation Mapping: Paper-to-Code

| Research Anchor | ArXiv ID | Theoretical Logic | Lab Implementation [FEAT] | Git Link | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FS-Researcher** | 2602.01566 | Dual-Agent: Context Builder + Report Writer | **Foundation:** `nibble.py` is the Context Builder [FEAT-095]. | [field_notes/nibble.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/nibble.py) | **100%** |
| **Agentic-R** | 2601.11888 | Learning to Retrieve: Utility-based ranking & Grep Pivot. | **Memory Bridge:** `ArchiveMemory` MMR ranking & fast Ripgrep pivot [FEAT-080/450/451]. | [nodes/archive_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/archive_node.py) | **100%** |
| **TTCS** | 2601.22628 | Test-Time Curriculum: Synthesizer + Solver. | **Quality:** Mitigates repetition loops via Synthesize-then-Solve patterns [FEAT-114]. | [field_notes/ai_engine_v2.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/ai_engine_v2.py) | **100%** |
| **Apple CLaRa** | 2511.18659 | Semantic Compression: 16x-128x density. | **Optimization:** `SemanticCondenser` compresses raw logs [FEAT-073]. | [field_notes/ai_engine_v2.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/ai_engine_v2.py) | **100%** |
| **Liger Kernel** | 2410.10989 | Efficient Triton Kernels for LLM Training. | **Efficiency:** Maximizing 8B residency on 11GB VRAM [FEAT-031]. | [nodes/loader.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/loader.py) | **100%** |
| **RLM** | 2512.24601 | Context as a Code-Readable String. | **Discovery:** `peek_related_notes()` logic [FEAT-117]. | [nodes/archive_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/archive_node.py) | **100%** |
| **Swarm Delegation** | 2402.05120 | Agentic Swarm Blueprint & Socket Activation Proxy. | **Orchestration:** OpenAgent REST session dispatcher [BKM-034]. | [src/tests/delegate.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/tests/delegate.py) | **100%** |
| **Tri-Node Routing** | 2405.07437 | Multi-Node Heterogeneous Telemetry & Reasoning. | **Federation:** Tri-Node evaluation & fallback ledger [SPR-47.1]. | [src/tests/test_integration_tri_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/tests/test_integration_tri_node.py) | **100%** |
| **TTT-Discover** | 2601.16175 | Test-Time Discovery: RL-based optimization. | **Automation:** Planned: RL loops for bug reproduction. | N/A | **0%** |
| **Dreaming** | 2603.04257 | Subconscious Compression (Memex). | **Consolidation:** `dream_cycle.py` moving logs to Wisdom [FEAT-067]. | [dream_cycle.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/dream_cycle.py) | **100%** |
| **Internal Debate** | 2603.00142 | Moderated Consensus (Byzantine ToM). | **Consensus:** `delegate_internal_debate` facilitates reasoning [FEAT-071]. | [logic/cognitive_hub.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/logic/cognitive_hub.py) | **100%** |
| **AT2QA** | 2603.01853 | Autonomous Exploration Pivot. | **Autonomy:** [FEAT-173] Pivot-query logic pass for thin results. | [logic/cognitive_hub.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/logic/cognitive_hub.py) | **Design** |
| **Agentic FS** | 2602.20478 | Context as a File System. | **Grounding:** Validates our "Static Synthesis" architecture. | [field_notes/mass_scan.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/mass_scan.py) | **100%** |
| **13-Param Reason** | 2602.04118 | Extreme parameter efficiency. | **Sentinel:** Optimization logic for 1B "Sentinel" mice nodes. | [nodes/lab_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/lab_node.py) | **Active** |
| **REDSearcher** | 2602.14234 | Long-Horizon Search Scaling. | **Discovery:** framework for deep technical history discovery. | [nodes/archive_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/archive_node.py) | **Design** |
| **VibeThinker-3B** | 2606.16140 | Verifiable Reasoning / Spectrum-to-Signal. | **Sanity:** Unified local base model for Phase 10 [FEAT-368]. | [nodes/loader.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/loader.py) | **Active** |
| **MCompassRAG** | 2606.18508 | Metadata as semantic compass. | **Discovery:** Planned: Metadata-guided paragraph RAG. | [nodes/archive_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/archive_node.py) | **Design** |
| **HyDE** | 2212.10496 | Hypothetical Document Embeddings. | **Open HyDE Preprocessor:** Pinky's streaming preamble generates hypotheses [FEAT-432]. | [nodes/archive_node.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/archive_node.py) | **75%** |
| **Query2Doc** | 2303.07678 | Fine-Tuning LLMs for Pseudo-Document Expansion. | **LoRA HyDE:** `cli_voice_v1` LoRA trained to emit dense acronyms & BKMs [SPR-58.0]. | [src/forge/train_expert.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/forge/train_expert.py) | **75%** |
| **GenRead** | 2209.10063 | Parametric Context Generation for Dense Retrieval. | **Jeopardy Distillation:** `distill_journal_ledger()` trains LoRA on bidirectional gem triggers [SPR-58.0]. | [field_notes/mass_scan.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/mass_scan.py) | **80%** |
| **Self-RAG** | 2310.11511 | Learning to Retrieve, Generate, and Critique via Reflection. | **Refinement Loop:** Tri-Field Gem Schemas & Hybrid RiR Gating [SPR-58.0]. | [field_notes/refine_gem.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/refine_gem.py) | **60%** |
| **Thinking to Recall** | 2603.09906 | Uses CoT as a computational buffer for factual priming. | Implemented via [FEAT-114] TTCS logic. | [field_notes/ai_engine_v2.py](https://github.com/kEnder242/Portfolio_Dev/blob/main/field_notes/ai_engine_v2.py) | **100%** |
| **AutoHarness** | 2603.03329 | Synthesizing Python guardrails for agent self-verification. | Grounds future [FEAT-353] Verifier Synthesis. | N/A | **Planned** |
| **Stochastic KV Routing** | 2604.22782 | Adaptive depth-wise cache sharing (Apple MLR). | Optimization pattern for [FEAT-031] Liger. | [nodes/loader.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/loader.py) | **Active** |
| **ARIS** | 2605.03042 | Adversarial multi-agent collaboration for research. | Theoretical base for [FEAT-071] Internal Debate. | [logic/cognitive_hub.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/logic/cognitive_hub.py) | **100%** |
| **CodeTracer** | 2604.11641 | Traceable agent states & failure onset localization. | Enhanced [FEAT-151] Forensic Ledger visibility. | [debug/test_forensic_logging.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/debug/test_forensic_logging.py) | **100%** |
| **PersonaVLM** | 2604.13074 | Proactive memory extraction & response alignment. | Core logic for [FEAT-067] Subconscious Dreaming. | [dream_cycle.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/dream_cycle.py) | **100%** |
| **TriAttention** | 2604.04921 | Trigonometric KV compression (10x reduction). | Future optimization for [FEAT-031] VRAM efficiency. | [nodes/loader.py](https://github.com/kEnder242/HomeLabAI/blob/main/src/nodes/loader.py) | **Active** |

