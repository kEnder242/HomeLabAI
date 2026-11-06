# Diagnostic Script Map: The Physician's Ledger
**Role: [LEDGER] - Instrument Inventory**

> [!IMPORTANT]
> **PURPOSE:** A mapping of every physical script, test, and verification tool.
> **Tags**: [WD] Watchdog Logic | [PING] Health Probe | [SMOKE] Validation Cycle.

---

## 🏗️ 1. Phase 19 Modern Core & Decoupled Accountability (BKM-066 / BKM-067)
These tools provide modern out-of-band accountability grading, synthetic round table verification, and instant dialogue extraction.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-001] Decoupled Watchdog** | `src/infra/standalone_accountability_watchdog.py` | **ACTIVE** | [FEAT-619 / BKM-066] Independent 06:00 AM sentry grading 7 vectors, lockfiles, and dead PIDs. |
| **[SCR-002] Round Table Turn Reader** | `src/infra/read_roundtable_turn.py` | **ACTIVE** | [FEAT-607 / BKM-067] High-speed CLI extractor for multi-turn dialogue from JSONL stream traces. |
| **[SCR-003] Synthetic RT Probe** | `src/infra/probe_round_table_accountability.py` | **ACTIVE** | [FEAT-608] Automated multi-resident verification suite (Greeting + Deliberation + Critic). |
| **[SCR-004] Watchdog Unit Tests** | `src/tests/test_standalone_accountability_watchdog.py` | **ACTIVE** | Unit test suite for out-of-band state age, dead PIDs, and digest double-write buffering. |
| **[SCR-005] Attendant Liveliness** | `src/attendant_liveliness.py` | **ACTIVE** | Verifies Lab Attendant REST API and absolute MD5 Lab Key security. |
| **[SCR-006] Intent Recall** | `src/tests/test_intent_recall.py` | **ACTIVE** | Verifies BKM-015.1 semantic intent identification for historical queries. |
| **[SCR-007] RAG Multi-Stage** | `src/test_rag_logic.py` | **ACTIVE** | Verifies Discovery (ChromaDB) -> Acquisition (Filesystem) path. |
| **[SCR-008] Visibility Truth** | `src/tests/test_visibility_truth.py` | **ACTIVE** | Playwright auditor verifying 100% transparency of `<thought>` tags in DOM. |
| **[SCR-009] Uber 5x5 Hand-Crank** | `src/debug/uber_5x5_hand_crank.py` | **STRESS** | **ULTIMATE.** 75-min gauntlet testing H2->Operational natural drift. |
| **[SCR-010] Empirical Step Harness** | `src/debug/test_empirical_step_harness.py` | **ACTIVE** | [FEAT-668 / BKM-088] Isolated deterministic micro-harness for empirical prompt shootouts. |

---

## 🏎️ 2. Silicon & VRAM (Hardware Profiling)
These tools verify that the Lab's weights fit within the 11GB VRAM budget and that high-throughput kernels (Liger) are active.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-011] Hardware Grounding** | `src/tests/test_hardware_grounding.py` | **LEGACY** | [PHASE 7] Verifies real-time telemetry tools (`get_lab_health`) and engine priming. |
| **[SCR-012] Engine Swap** | `src/debug/test_engine_swap.py` | **STALE** | Verifies the hot-swap from vLLM to Ollama fallback during moderate VRAM pressure. |
| **[SCR-013] Apollo 11** | `src/debug/test_apollo_vram.py` | **GEM** | **CRITICAL.** Profiles active inference peak. Runs "Token Burn" to verify headroom. |
| **[SCR-014] VRAM Guard** | `src/test_vram_guard.py` | **ACTIVE** | Validates the "Stub" fallback logic when VRAM is >95% or engines fail to load. |
| **[SCR-015] SIGTERM Protocol** | `src/debug/test_sigterm_protocol.py` | **STALE** | Verifies dynamic pre-emption and the flexible SIGTERM sequence. |
| **[SCR-016] Liger Test** | `src/test_liger.py` | **LEGACY** | Specifically verifies that Liger-Kernels are accelerating the vLLM engine. |
| **[SCR-017] VLLM Alpha** | `src/debug/test_vllm_alpha.py` | **STALE** | Low-level connectivity check for the vLLM OpenAI-compatible endpoint. |
| **[SCR-018] MPS Stress** | `src/debug/mps_stress.py` | **LEGACY** | Legacy stress test for MPS (Metal) performance; maintained for cross-platform baseline. |

---

## ⚙️ 3. Lifecycle & Orchestration (The Attendant)
These tools verify the `systemd` managed infrastructure and the Hub's resilience to state transitions.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-019] Live Fire Triage** | `src/debug/test_live_fire_triage.py` | **ACTIVE** | [FEAT-203] Active Auditor. Rapid verification of parallel turn-bundling. |
| **[SCR-020] JSON Fix Experiment** | `src/debug/experiment_json_fix.py` | **LEGACY** | [DEBUG] Standalone testbed for the Bicameral Bridge signal cleaning regex patterns. |
| **[SCR-021] Strategic Live Fire** | `src/tests/test_strategic_live_fire.py` | **STALE** | [PHASE 7] **DEFINITIVE.** End-to-end physical hardware validation. |
| **[SCR-022] Gauntlet** | `src/debug/test_lifecycle_gauntlet.py` | **STRESS** | Stress tests the Hub with rapid connect/disconnect cycles. |
| **[SCR-023] Goodnight Bounce** | `src/debug/test_goodnight_bounce.py` | **STALE** | [FEAT-149] Verifies appliance-grade resilience and auto-restart loop. |
| **[SCR-024] Attendant Sanity** | `src/debug/test_attendant_sanity.py` | **ACTIVE** | [WD] Verifies the Lab Attendant's HTTP API (Start/Stop/Status/Wait_Ready). |
| **[SCR-025] Shutdown Resilience** | `src/debug/test_shutdown_resilience.py` | **ACTIVE** | Verifies that the Lab can shut down via native tool flow. |
| **[SCR-026] Shutdown Flow** | `src/test_shutdown.py` | **ACTIVE** | Validates clean exit sequences and PID cleanup for all lab processes. |
| **[SCR-027] Interrupt Test** | `src/test_interrupt.py` | **ACTIVE** | Tests handling of SIGINT/KeyboardInterrupt across the multi-process stack. |

---

## 🎭 4. Persona & Banter (The "Soul")
Ensures the Lab maintains its Bicameral character without falling into "Chatter Traps" or repetitive loops.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-028] Morning Briefing** | `src/tests/test_vibe_triggers.py` | **ACTIVE** | [PHASE 7] Verifies semantic trigger for news/updates based on intent vibe. |
| **[SCR-029] Latency Tics** | `src/test_latency_tics.py` | **ACTIVE** | Verifies that Pinky sends "Thinking" tics during long reasoning cycles. |
| **[SCR-030] Persona Audit** | `src/debug/test_persona_bugs.py` | **GEM** | Checks for verbosity issues and ensures "Certainly!" filler is stripped. |
| **[SCR-031] Contextual Echo** | `src/debug/test_contextual_echo.py` | **STALE** | Verifies persona-aware echo behavior. |
| **[SCR-032] MIB Wipe** | `src/debug/test_mib_wipe.py` | **GEM** | Verifies the "Neuralyzer" memory clearing mechanic and context cap. |
| **[SCR-033] Banter Decay** | `src/debug/test_banter_decay.py` | **ACTIVE** | Verifies that reflexes slow down correctly during idle states. |
| **[SCR-034] Neural Probe** | `src/debug/probe_hub.py` | **STALE** | [PING] Sniffs internal Hub hints (Exit Sentiment, Strategic Intent). |
| **[SCR-035] Echo Check** | `src/test_echo.py` | **LEGACY** | Verifies basic text/binary processing in the "Talk & Read" loop. |
| **[SCR-036] Intercom Flow** | `src/test_intercom_flow.py` | **ACTIVE** | End-to-end test of the CLI `intercom.py` client communication. |

---

## 🧠 5. Bicameral Logic (Hemispheric Crosstalk)
Validates "Thought Partner" capabilities, including delegation, tool access, and directness.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-037] Agentic Backtrack** | `src/tests/test_agentic_backtrack.py` | **GEM** | [PHASE 7] Verifies the Hallway Protocol and Strategic Pivot logic for Agentic-R. |
| **[SCR-038] Pi Flow** | `src/debug/test_pi_flow.py` | **ACTIVE** | **CRITICAL.** Verifies the "Direct Answer First" rule. |
| **[SCR-039] Ghost Tool Sentry** | `src/tests/test_tool_validation.py` | **GEM** | [PHASE 7] Verifies detection and shunting of hallucinated tools. |
| **[SCR-040] Iron Gate Audit** | `src/debug/gate_triage_audit.py` | **STALE** | Verifies the hardened gate for casual vs. strategic triage. |
| **[SCR-041] Dispatch Logic** | `src/debug/test_dispatch_logic.py` | **ACTIVE** | Verifies the hardened priority dispatcher and hallucination shunt. |
| **[SCR-042] Round Table** | `src/test_round_table.py` | **ACTIVE** | Validates the Pinky -> Brain handover logic and shared context persistence. |
| **[SCR-043] Tool Registry** | `src/debug/test_tool_registry.py` | **GEM** | [PING] **CRITICAL.** Confirms all physical MCP tools are visible to agents. |
| **[SCR-044] Strategic Sentinel** | `src/debug/test_strategic_sentinel.py` | **STALE** | Verifies Amygdala filtering and typing-aware reflex suppression. |
| **[SCR-045] Resurrection Tools** | `src/debug/test_resurrection_tools.py` | **ACTIVE** | Verifies high-value restored tools: CV Builder, BKM Generator. |
| **[SCR-046] Architect Flow** | `src/debug/test_architect_flow.py` | **STALE** | Validates the Architect Node's BKM synthesis logic. |
| **[SCR-047] Draft Agency** | `src/test_draft_agency.py` | **STALE** | Tests the `write_draft` tool and the "Editor Cleaning" pattern. |
| **[SCR-048] MCP Integration** | `src/test_mcp_integration.py` | **GEM** | Verifies low-level MCP server handshakes and tool discovery. |

---

## ⚒️ 6. The Forge (LoRA Synthesis)
Tools for distilling technical pedigree into specialized training data.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-049] Deep-Connect Capture** | `src/forge/deep_connect_epoch_v2.py` | **ACTIVE** | [FEAT-202] Stage 1 Capture. Background harvest of raw technical blocks. |
| **[SCR-050] Surgical Refinement** | `src/forge/refine_bones.py` | **ACTIVE** | [FEAT-202] Stage 2 Refine. Signal cleaning pass for high-density BKM pairs. |
| **[SCR-051] Prompt Extractor** | `src/forge/extract_gemini_prompts.py` | **GEM** | [FEAT-204] Aggregates multi-year CLI prompt history for Persona Induction. |
| **[SCR-052] Distill Forge** | `src/forge/distill_gems.py` | **ACTIVE** | Transforms Rank 4 gems into high-density LoRA training pairs. |
| **[SCR-053] Expert Forge** | `src/train/train_expert.py` | **GEM** | Unsloth scaffolding for local 2080 Ti fine-tuning. |

---

## 💾 7. Data & Memory (The Archives)
Verifies the transition from raw logs to synthesized "Diamond" wisdom.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-054] Dream Test** | `src/test_dream.py` | **ACTIVE** | Validates the memory consolidation pipeline (`dream_cycle.py`). |
| **[SCR-055] Memory Sync** | `src/test_memory_integration.py` | **GEM** | Verifies the end-to-end RAG path (ChromaDB + Embedding Server). |
| **[SCR-056] Cache Check** | `src/test_cache_integration.py` | **STALE** | Verifies semantic cache lookups ("Consult Clipboard"). |
| **[SCR-057] Dedup Check** | `src/test_dedup.py` | **ACTIVE** | Validates semantic de-duplication of archived notes. |
| **[SCR-058] Save Flow** | `src/test_save_flow.py` | **STALE** | Validates the "Strategic Vibe Check" triggered by manual file saves. |
| **[SCR-059] Pager Atomic** | `src/debug/test_pager_atomic.py` | **ACTIVE** | [FEAT-298] Verifies BKM-022 atomic swap protocol for the UI forensic ledger. |
| **[SCR-060] Recruiter Match** | `src/test_recruiter.py` | **STALE** | Verifies the nightly job-matching logic against the CV summary. |

---

## 🎙️ 8. Audio & Streaming (The Sensory Node)
Verifies the NeMo-based EarNode and real-time STT capabilities.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-061] Audio Pipeline** | `src/test_audio_pipeline.py` | **ACTIVE** | Tests the Float32 -> Int16 conversion and STT streaming path. |
| **[SCR-062] GUI Flows** | `src/debug/test_gui_flows.py` | **ACTIVE** | Verifies browser-to-server UI event handshakes. |
| **[SCR-063] EarNode Isolated** | `src/test_earnode_isolated.py` | **GEM** | Verifies EarNode initialization and CUDA Graph behavior. |
| **[SCR-064] Web Binary** | `src/debug/test_web_binary.py` | **STALE** | Tests the integrity of audio chunks sent via WebSocket binary frames. |

---

## 📡 9. The Scouts & Logic (New Nodes)
Extended capabilities for live research and structured thinking.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-065] Browser Probe** | `src/test_browser_isolated.py` | **ACTIVE** | Verifies Playwright initialization in the Browser Node. |
| **[SCR-066] Sequential Thinking** | `src/test_thinking_node.py` | **ACTIVE** | Verifies stateful multi-step reasoning chains. |

---

## 🏗️ 10. Scanner & Synthesis (Background Recovery)
Surgical tools for the Portfolio_Dev "Face" pipeline. Use these when the Slow Burn stalls or parity is lost.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-067] Mass Scan Engine** | `Portfolio_Dev/field_notes/mass_scan.py` | **ACTIVE** | [P9] Continuous background scanner processing the 18-year archive. |
| **[SCR-068] Site Synthesizer** | `Portfolio_Dev/field_notes/build_site.py` | **ACTIVE** | Compiles static search index and cache-busted HTML pages. |
| **Artifact Sync** | `src/bridge_burn_to_rag.py` | [NEW] Indexes the physical asset catalog (files.html) into RAG. |

---

## 🤖 11. Delegation & Swarm Orchestration (BKM-034)
Helper scripts and execution wrappers for delegating development stories to OpenAgent swarms on port 4096.

| **[SCR-069] Delegation Launcher** | `src/tests/delegate.py` | **ACTIVE** | [BKM-034/BKM-042] [GOLD] Standard OpenAgent story dispatch harness via port 4097 REST API. Supports `--reference`, `--target`, `--mode`, and `--verification`. |
| **[SCR-070] Live Lab Gauntlet** | `src/tests/run_live_lab_gauntlet.sh` | **ACTIVE** | [SPR-53.0] [GOLD] Unified non-mocked integration test runner calling live endpoints (`:8088`, `:8765`, `:9090`, `:11434`). |
| **[SCR-071] Adapter Swap Test** | `src/tests/test_vllm_adapter_swap.py` | **ACTIVE** | [SPR-52.0] Verifies zero-downtime hot-reload contract for `cli_voice_v1` LoRA adapter on vLLM. |
| **[SCR-072] Scratch Delegate** | `src/tests/scratch_delegate.py` | **LEGACY** | [BKM-034] Legacy CLI wrapper; replaced by REST API `delegate.py`. |
| **Nudge 2024** | `field_notes/nudge_2024.py` | [RECOVERY] Clears hash for 2024 files to force a targeted re-nibble. |
| **Clean Data** | `field_notes/clean_data.py` | **DANGER.** Wipes the data directory. |

---

## 🧬 12. Nightly Forge & Distillation Diagnostics (Sprint 58)
Diagnostic and shakedown instruments validating the production infrastructure (`src/infra/nightly_forge.py`, `refine_gem.py`, and `mass_scan.py`).

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-073] Agentic-R Retrieval Test** | `src/tests/test_agentic_r_retrieval.py` | **ACTIVE** | [SPR-58.0] [GOLD] Unit test suite verifying Maximal Marginal Relevance (MMR) novelty re-ranking and Ripgrep autonomous search pivot. |
| **[SCR-074] Forge Distillation Unit** | `src/tests/test_forge_distillation_unit.py` | **ACTIVE** | [SPR-58.0] [GOLD] Unit test suite verifying Tri-Field schema parsing, backward compatibility, code artifact Jeopardy pairs, and 590+ dataset integrity. |
| **[SCR-075] Nightly Forge Shakedown** | `src/tests/test_nightly_forge_shakedown.py` | **ACTIVE** | [SPR-58.0] [GOLD] Full end-to-end integration shakedown verifying module imports, REST quiesce/re-ignite contracts, train_expert dataset mapping, and dreaming subprocess handling. |

---

## 🛰️ 13. Modular Satellite & Epistemic Instruments (Sprint 59)
Diagnostic and verification test suites validating the Sprint 59 Modular Satellite architecture, deterministic evaluation batteries, and live co-pilot feedback loops.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-076] Sprint 59 Integration Suite** | `src/tests/test_sprint59_integration.py` | **ACTIVE** | [SPR-59.0] [GOLD] Full-loop integration test suite validating Fourth Wall critique interception, Floating Oracle candidate pool injection, live AST context compaction, and Epistemic evaluator consistency (4/4 tests). |
| **[SCR-077] Universal Epistemic Evaluator** | `src/tests/test_binary_evaluator_unit.py` | **ACTIVE** | [SPR-59.0] [FEAT-454] Unit test suite verifying 0% score drift and deterministic Rank = min(5, 1+sum(bool)) across 5 boolean checks (31/31 tests). |
| **[SCR-078] AST Context Compiler Unit** | `src/tests/test_context_compiler.py` | **ACTIVE** | [SPR-59.0] [FEAT-455] Unit test suite verifying AST symbol extraction, function body stripping, >50% token compaction, and cross-module dependency trees (22/22 tests). |
| **[SCR-079] Fourth Wall Interceptor Unit** | `src/tests/test_feedback_interceptor.py` | **ACTIVE** | [SPR-59.0] [FEAT-456/BKM-035] Unit test suite verifying linguistic critique detection, BKM-022 atomic JSONL write, and in-character refinement prompt generation (30/30 tests). |
| **[SCR-080] Floating Validation Oracle Unit** | `src/tests/test_floating_oracle.py` | **ACTIVE** | [SPR-59.0] [FEAT-458] Unit test suite verifying candidate harvesting, missing-file fallbacks, candidate pool formatting, and shallow turn classification (53/53 tests). |
| **[SCR-081] Speculative Pre-fetch Unit** | `src/tests/test_interest_speculative_prefetch.py` | **ACTIVE** | [SPR-59.0] [FEAT-457] Unit test suite verifying Turn 1 background RAG pre-fetch and interest preemption (2/2 tests). |

---
**Standard Certification Runner**:
```bash
PYTHONPATH=. python -m pytest src/tests/test_sprint59_integration.py \
                             src/tests/test_binary_evaluator_unit.py \
                             src/tests/test_context_compiler.py \
                             src/tests/test_feedback_interceptor.py \
                             src/tests/test_interest_speculative_prefetch.py \
                             src/tests/test_floating_oracle.py
```

---

## 14. Sprint 60 Modular Satellite Decompositions & Boundary Test Suites (SPR-60.0)

| Script Path | Purpose & Mechanics | Core Triggers & Verification |
| :--- | :--- | :--- |
| `src/tests/test_override_parser.py` | **Override Parser Satellite Unit Suite [FEAT-145/REF-01]**<br>Tests query intent detection (`GEM-xxxx`/`BKM-xxx`), resident JSON extraction, and atomic disk persistence (`overrides.json`). | `pytest src/tests/test_override_parser.py` (28 unit tests, <0.25s) |
| `src/tests/test_maintenance_sweeper.py` | **Maintenance Sweeper Satellite Unit Suite [LAB-095/096/099/REF-02]**<br>Tests CPU package thermal zones (`/sys/class/thermal`), heap garbage collection (`gc.collect()`), and safe TTL buffer pruning without `KeyError`. | `pytest src/tests/test_maintenance_sweeper.py` (23 unit tests, <0.40s) |
| `src/tests/test_audio_pipeline.py` | **Audio Pipeline Satellite Unit Suite [FEAT-059/LAB-088/REF-03]**<br>Tests signed int16 PCM buffer conversions, 24000/16000 sliding window extraction, and int32-widened peak amplitude detection. | `pytest src/tests/test_audio_pipeline.py` (19 unit tests, <0.30s) |
| `src/tests/test_sprint60_integration.py` | **Sprint 60 In-Process Integration Gauntlet**<br>Validates the interaction of all three decoupled satellites with core orchestrators (`CognitiveHub`, `SensoryManager`, `router.py`). | `pytest src/tests/test_sprint60_integration.py` (4 integration tests) |
| `src/tests/test_live_sprint60_e2e.py` | **Sprint 60 Live-Fire Service Integration Suite (Story 60.5)**<br>Executes authenticated WebSocket transactions (`ws://127.0.0.1:8765`), sending live overrides, binary PCM frames, and heartbeat checks against the active running daemon. | `python3 src/tests/test_live_sprint60_e2e.py` (Live WebSocket) |

---
**Sprint 60 Certification Runner**:
```bash
PYTHONPATH=. python -m pytest src/tests/test_override_parser.py \
                             src/tests/test_maintenance_sweeper.py \
                             src/tests/test_audio_pipeline.py \
                             src/tests/test_sprint60_integration.py
```

---

## 15. Sprint 71 Live Elapsed Telemetry & Silicon Stability Gauntlet (SPR-71.0)
Verification instruments validating `FEAT-265` mandatory blocking status timeout, `FEAT-525` Live Round Table elapsed time checkpoints, and non-mocked physical silicon deliberations.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-082] Live Elapsed Time UI** | `src/tests/test_benchmarks_elapsed_time_ui.py` | **ACTIVE** | [FEAT-525] [GOLD] Playwright DOM test validating the "LIVE ROUND TABLE ELAPSED TIME" tab, canvas dimensions, and expandable "LIVE ELAPSED CHECKPOINTS" ledger drawer. |
| **[SCR-083] Sprint 71 Stability Gauntlet** | `src/tests/test_live_sprint71_stability.py` | **ACTIVE** | [FEAT-265/525] [GOLD] Live silicon test suite exercising fresh bytecode integrity, stale client commit rejection (WS 1008), dialogue roll-up, and full 5-stage Round Table deliberation timing. |

---
**Sprint 71 Certification Runner**:
```bash
PYTHONPATH=. python -m pytest src/tests/test_benchmarks_elapsed_time_ui.py \
                             src/tests/test_live_sprint71_stability.py -v
```

---

## 16. Sprint 86 DNA Dropped Ball, Draft Ingestion & Polymorphic Vector Diagnostics (SPR-86.0 / SPR-86.1)
Diagnostic, verification, and shakedown instruments validating the Sprint 86 Polymorphic DNA architecture, semantic draft decomposition, mutation governance, and ChromaDB vector synchronization.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-084] Paper Engine & Draft Decomposer** | `src/tests/test_paper_engine.py` | **ACTIVE** | [FEAT-597] [GOLD] Live silicon test validating AST lens crafting, citation expansion, connection graphs, and vLLM semantic draft decomposition. |
| **[SCR-085] Live Pre-Reflection Triage** | `src/tests/test_live_pre_reflection_triage.py` | **ACTIVE** | [FEAT-583/584/586] [GOLD] Live Foyer daemon integration suite verifying EWMA latency estimations, RDNA HyDE bypass (<0.45 distance), and triage engine preferences. |
| **[SCR-086] Journal-to-DNA Bridge** | `src/tests/test_journal_to_dna_bridge.py` | **ACTIVE** | [FEAT-592] [GOLD] Unit test suite verifying note ingestion extraction, gem fingerprinting idempotency, and polymorphic WIS card schema compliance. |
| **[SCR-087] Draft Promotion & Safe ID Allocation** | `src/tests/test_draft_promotion_unit.py` | **ACTIVE** | [FEAT-597/BKM-060] [GOLD] Unit test suite verifying collision-safe ID allocation across BKM, FEAT, RDNA, DISC and non-blocking background HTML rebuild dispatch. |
| **[SCR-088] Mutation Certification & Cleanup** | `src/tests/test_mutation_certification_unit.py` | **ACTIVE** | [FEAT-598] [GOLD] Unit test suite verifying certified mutation proposals are purged from candidate arrays while revision histories increment. |
| **[SCR-089] Polymorphic LoRA Dataset Invariant** | `src/tests/test_polymorphic_lora_dataset_unit.py` | **ACTIVE** | [FEAT-582] [GOLD] Unit test suite verifying polymorphic DNA dataset balance, 430+ FEAT section regex ingestion, and RDNA narrative context enrichment. |
| **[SCR-090] Schema Backfill Verification** | `../Portfolio_Dev/scripts/backfill_card_schema.py` | **ACTIVE** | [FEAT-582] Diagnostic migration script verifying 100% of WIS and PHL cards have initialized `mutations: []` and `revisions: []` structures. |
| **[SCR-091] ChromaDB Idempotency & Dry-Run** | `../Portfolio_Dev/sync_chroma_dna.py` | **ACTIVE** | [FEAT-582] Diagnostic probe testing ChromaDB sync state, SHA256 checksum caching (`.sync_checksums.json`), and `--dry-run` inspection. |

---
**Sprint 86 Certification Runner**:
```bash
PYTHONPATH=src python -m pytest src/tests/test_draft_promotion_unit.py \
                                src/tests/test_mutation_certification_unit.py \
                                src/tests/test_polymorphic_lora_dataset_unit.py \
                                src/tests/test_journal_to_dna_bridge.py \
                                src/tests/test_paper_engine.py \
                                src/tests/test_live_pre_reflection_triage.py -v
```

---

## 17. Sprint 103 Intercom Debug, Multi-Stage Replay & Stage Decoupling Diagnostics (SPR-103.0)
Verification instruments validating `FEAT-645` Multi-Stage Replay Pipeline Harness, `BKM-083` Decouple-and-Stitch stage isolation, un-muted Deep Thought live backchannel, and pure continuous interest pacing (`FEAT-523`).

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-092] Multi-Stage Replay Pipeline Harness** | `src/tests/test_multi_stage_replay_pipeline.py` | **ACTIVE** | [FEAT-645/BKM-083] [GOLD] Standalone offline integration suite validating all 5 round table stages (Pre-Triage $\to$ Triage $\to$ HyDE/RAG $\to$ Brain Gatekeeper $\to$ Deep Thought Strategic Synthesis / Pinky Voice) with frozen litmus fixtures. |
| **[SCR-093] Brain Epistemic Gatekeeper & Steering** | `src/tests/test_brain_gatekeeper.py` | **ACTIVE** | [FEAT-635] Validates Stage 1 Brain gatekeeper filtering of candidate RAG chunks and sideband curator note generation. |
| **[SCR-094] Two-Mice Handover & Tri-Node Relay** | `src/tests/test_two_mice_handover.py` | **ACTIVE** | [FEAT-489/FEAT-645] Validates sequential multi-node streaming handover across Right, Center, and Left consoles. |
| **[SCR-095] HyDE Resolution & Turn Isolation** | `src/tests/test_feat437_resolve_hyde_vector.py` | **ACTIVE** | [FEAT-437/FEAT-640] Validates HyDE vector generation with single-turn isolation and `search_required: bool` gating. |
| **[SCR-096] Round Table Telemetry Bridge** | `src/tests/test_round_table_telemetry.py` | **ACTIVE** | [FEAT-525] Validates physical silicon stopwatch recording into `round_table_deltas.json`. |

---
**Sprint 103 Replay Pipeline Certification Runner**:
```bash
PYTHONPATH=. python -m pytest src/tests/test_multi_stage_replay_pipeline.py -v
```
---

## 18. Modern Diagnostics & Verification Gauntlets (Sprints 104–110)
Verification instruments validating multi-node streaming handover, BKM-089 prompt asymmetry, BKM-090 step probes, Ripgrep multi-anchor hydration, and active ChromaDB DNA sync.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **[SCR-097] Ripgrep Hydration Bridge** | `src/tests/test_ripgrep_hydration.py` | **ACTIVE** | [FEAT-668 / FEAT-685] Multi-source anchor harvesting, discrete bucket quotas, and whole-word boundary verification across raw notes. |
| **[SCR-098] Live FastMCP Prober** | `src/debug/mcp_prober.py` | **ACTIVE** | [FEAT-673 / FEAT-679] Standalone sensory diagnostic tool verifying FastMCP server discovery, tool registration, and live hardware sensor payloads. |
| **[SCR-099] Career Compass Bedrock Suite** | `src/tests/test_career_compass_bedrock.py` | **ACTIVE** | [FEAT-683] Validates Tier 1 Career Bedrock extraction, completeness-of-era invariant, and zero-loss platform history indexing. |
| **[SCR-100] FeatureTracker Gatekeeper** | `src/tests/test_feature_tracker_gatekeeper.py` | **ACTIVE** | [FEAT-686] Automated pre-commit CI gatekeeper preventing ghost FEAT code comments and validating AST symbol references. |
| **[SCR-101] Pinky Critic Persona Suite** | `src/tests/test_pinky_critic_persona.py` | **ACTIVE** | [FEAT-661 / BKM-089] 102-test verification battery for 3B Pinky voice, zero 3rd-person leaks, and out-of-band entailment auditing. |
| **[SCR-102] Feedback Semantic Triage Suite** | `src/tests/test_feedback_semantic_triage.py` | **ACTIVE** | [FEAT-559 / BKM-015] Semantic triage intent domain classification and prompt-guided foil evaluation with zero brittle regex. |
| **[SCR-103] Round Table Probe Unit Suite** | `src/tests/test_round_table_probe_unit.py` | **ACTIVE** | [FEAT-608 / BKM-024] Unit suite for physical multi-node synthetic round table probes and judicial consensus checks. |
| **[SCR-104] Cognitive Hub Pacing Suite** | `src/tests/test_cognitive_hub_pacing.py` | **ACTIVE** | [FEAT-523 / FEAT-658] Continuous interest pacing, sideband consensus, and multi-turn interest decay mathematics. |
| **[SCR-105] Censorship Memory Tri-Node Suite** | `src/tests/test_censorship_memory_tri_node.py` | **ACTIVE** | [FEAT-361 / FEAT-558] Zero-censorship audit asserting complete transparency of internal reflection streams across UI channels. |
