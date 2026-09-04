# Diagnostic Script Map: The Physician's Ledger
**Role: [LEDGER] - Instrument Inventory**

> [!IMPORTANT]
> **PURPOSE:** A mapping of every physical script, test, and verification tool.
> **Tags**: [WD] Watchdog Logic | [PING] Health Probe | [SMOKE] Validation Cycle.

---

## 🏗️ 1. Phase 15 Core (Neural Relay)
These tools are the "Gold Master" baseline for the current Sprint 31 Refactor Readiness.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Attendant Liveliness**| `src/attendant_liveliness.py`| **ACTIVE** | [NEW] Verifies Lab Attendant REST API and absolute MD5 Lab Key security. |
| **Liveliness** | `src/test_liveliness.py` | **ACTIVE** | Heartbeat check. Verifies the WebSocket port is open and `READY` state is achievable. |
| **Intent Recall** | `src/tests/test_intent_recall.py`| **ACTIVE** | [NEW] Verifies BKM-015.1 semantic intent identification for historical queries. |
| **RAG Multi-Stage** | `src/test_rag_logic.py` | **ACTIVE** | Verifies Discovery (ChromaDB) -> Acquisition (Filesystem) path. |
| **Visibility Truth** | `src/tests/test_visibility_truth.py`| **ACTIVE** | [NEW] Playwright auditor verifying 100% transparency of `<thought>` tags in DOM. |
| **Uber 5x5 Hand-Crank**| `src/debug/uber_5x5_hand_crank.py`| **STRESS** | **ULTIMATE.** 75-min gauntlet testing H2->Operational natural drift. |

---

## 🏎️ 2. Silicon & VRAM (Hardware Profiling)
These tools verify that the Lab's weights fit within the 11GB VRAM budget and that high-throughput kernels (Liger) are active.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Hardware Grounding**| `src/tests/test_hardware_grounding.py`| **LEGACY** | [PHASE 7] Verifies real-time telemetry tools (`get_lab_health`) and engine priming. |
| **Engine Swap** | `src/debug/test_engine_swap.py` | **STALE** | Verifies the hot-swap from vLLM to Ollama fallback during moderate VRAM pressure. |
| **Apollo 11** | `src/debug/test_apollo_vram.py` | **GEM** | **CRITICAL.** Profiles active inference peak. Runs "Token Burn" to verify headroom. |
| **VRAM Guard** | `src/test_vram_guard.py` | **ACTIVE** | Validates the "Stub" fallback logic when VRAM is >95% or engines fail to load. |
| **SIGTERM Protocol** | `src/debug/test_sigterm_protocol.py` | **STALE** | Verifies dynamic pre-emption and the flexible SIGTERM sequence. |
| **Liger Test** | `src/test_liger.py` | **LEGACY** | Specifically verifies that Liger-Kernels are accelerating the vLLM engine. |
| **VLLM Alpha** | `src/debug/test_vllm_alpha.py` | **STALE** | Low-level connectivity check for the vLLM OpenAI-compatible endpoint. |
| **MPS Stress** | `src/debug/mps_stress.py` | **LEGACY** | Legacy stress test for MPS (Metal) performance; maintained for cross-platform baseline. |

---

## ⚙️ 3. Lifecycle & Orchestration (The Attendant)
These tools verify the `systemd` managed infrastructure and the Hub's resilience to state transitions.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Live Fire Triage**| `src/debug/test_live_fire_triage.py`| **ACTIVE** | [FEAT-203] Active Auditor. Rapid verification of parallel turn-bundling. |
| **JSON Fix Experiment**| `src/debug/experiment_json_fix.py`| **LEGACY** | [DEBUG] Standalone testbed for the Bicameral Bridge signal cleaning regex patterns. |
| **Strategic Live Fire**| `src/tests/test_strategic_live_fire.py`| **STALE** | [PHASE 7] **DEFINITIVE.** End-to-end physical hardware validation. |
| **Gauntlet** | `src/debug/test_lifecycle_gauntlet.py` | **STRESS** | Stress tests the Hub with rapid connect/disconnect cycles. |
| **Goodnight Bounce**| `src/debug/test_goodnight_bounce.py`| **STALE** | [FEAT-149] Verifies appliance-grade resilience and auto-restart loop. |
| **Attendant Sanity** | `src/debug/test_attendant_sanity.py` | **ACTIVE** | [WD] Verifies the Lab Attendant's HTTP API (Start/Stop/Status/Wait_Ready). |
| **Shutdown Resilience**| `src/debug/test_shutdown_resilience.py`| **ACTIVE** | Verifies that the Lab can shut down via native tool flow. |
| **Shutdown Flow** | `src/test_shutdown.py` | **ACTIVE** | Validates clean exit sequences and PID cleanup for all lab processes. |
| **Interrupt Test** | `src/test_interrupt.py` | **ACTIVE** | Tests handling of SIGINT/KeyboardInterrupt across the multi-process stack. |

---

## 🎭 4. Persona & Banter (The "Soul")
Ensures the Lab maintains its Bicameral character without falling into "Chatter Traps" or repetitive loops.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Morning Briefing** | `src/tests/test_vibe_triggers.py` | **ACTIVE** | [PHASE 7] Verifies semantic trigger for news/updates based on intent vibe. |
| **Latency Tics** | `src/test_latency_tics.py` | **ACTIVE** | Verifies that Pinky sends "Thinking" tics during long reasoning cycles. |
| **Persona Audit** | `src/debug/test_persona_bugs.py` | **GEM** | Checks for verbosity issues and ensures "Certainly!" filler is stripped. |
| **Contextual Echo** | `src/debug/test_contextual_echo.py` | **STALE** | Verifies persona-aware echo behavior. |
| **MIB Wipe** | `src/debug/test_mib_wipe.py` | **GEM** | Verifies the "Neuralyzer" memory clearing mechanic and context cap. |
| **Banter Decay** | `src/debug/test_banter_decay.py`| **ACTIVE** | Verifies that reflexes slow down correctly during idle states. |
| **Neural Probe** | `src/debug/probe_hub.py` | **STALE** | [PING] Sniffs internal Hub hints (Exit Sentiment, Strategic Intent). |
| **Echo Check** | `src/test_echo.py` | **LEGACY** | Verifies basic text/binary processing in the "Talk & Read" loop. |
| **Intercom Flow** | `src/test_intercom_flow.py` | **ACTIVE** | End-to-end test of the CLI `intercom.py` client communication. |

---

## 🧠 5. Bicameral Logic (Hemispheric Crosstalk)
Validates "Thought Partner" capabilities, including delegation, tool access, and directness.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Agentic Backtrack** | `src/tests/test_agentic_backtrack.py` | **GEM** | [PHASE 7] Verifies the Hallway Protocol and Strategic Pivot logic for Agentic-R. |
| **Pi Flow** | `src/debug/test_pi_flow.py` | **ACTIVE** | **CRITICAL.** Verifies the "Direct Answer First" rule. |
| **Ghost Tool Sentry** | `src/tests/test_tool_validation.py` | **GEM** | [PHASE 7] Verifies detection and shunting of hallucinated tools. |
| **Iron Gate Audit** | `src/debug/gate_triage_audit.py`| **STALE** | Verifies the hardened gate for casual vs. strategic triage. |
| **Dispatch Logic** | `src/debug/test_dispatch_logic.py` | **ACTIVE** | Verifies the hardened priority dispatcher and hallucination shunt. |
| **Round Table** | `src/test_round_table.py` | **ACTIVE** | Validates the Pinky -> Brain handover logic and shared context persistence. |
| **Tool Registry** | `src/debug/test_tool_registry.py` | **GEM** | [PING] **CRITICAL.** Confirms all physical MCP tools are visible to agents. |
| **Strategic Sentinel**| `src/debug/test_strategic_sentinel.py`| **STALE** | Verifies Amygdala filtering and typing-aware reflex suppression. |
| **Resurrection Tools**| `src/debug/test_resurrection_tools.py`| **ACTIVE** | Verifies high-value restored tools: CV Builder, BKM Generator. |
| **Architect Flow** | `src/debug/test_architect_flow.py` | **STALE** | Validates the Architect Node's BKM synthesis logic. |
| **Draft Agency** | `src/test_draft_agency.py` | **STALE** | Tests the `write_draft` tool and the "Editor Cleaning" pattern. |
| **MCP Integration** | `src/test_mcp_integration.py` | **GEM** | Verifies low-level MCP server handshakes and tool discovery. |

---

## ⚒️ 6. The Forge (LoRA Synthesis)
Tools for distilling technical pedigree into specialized training data.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Deep-Connect Capture**| `src/forge/deep_connect_epoch_v2.py`| **ACTIVE** | [FEAT-202] Stage 1 Capture. Background harvest of raw technical blocks. |
| **Surgical Refinement**| `src/forge/refine_bones.py`| **ACTIVE** | [FEAT-202] Stage 2 Refine. Signal cleaning pass for high-density BKM pairs. |
| **Prompt Extractor** | `src/forge/extract_gemini_prompts.py` | **GEM** | [FEAT-204] Aggregates multi-year CLI prompt history for Persona Induction. |
| **Distill Forge** | `src/forge/distill_gems.py` | **ACTIVE** | Transforms Rank 4 gems into high-density LoRA training pairs. |
| **Expert Forge** | `src/train/train_expert.py` | **GEM** | Unsloth scaffolding for local 2080 Ti fine-tuning. |

---

## 💾 7. Data & Memory (The Archives)
Verifies the transition from raw logs to synthesized "Diamond" wisdom.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Dream Test** | `src/test_dream.py` | **ACTIVE** | Validates the memory consolidation pipeline (`dream_cycle.py`). |
| **Memory Sync** | `src/test_memory_integration.py` | **GEM** | Verifies the end-to-end RAG path (ChromaDB + Embedding Server). |
| **Cache Check** | `src/test_cache_integration.py` | **STALE** | Verifies semantic cache lookups ("Consult Clipboard"). |
| **Dedup Check** | `src/test_dedup.py` | **ACTIVE** | Validates semantic de-duplication of archived notes. |
| **Save Flow** | `src/test_save_flow.py` | **STALE** | Validates the "Strategic Vibe Check" triggered by manual file saves. |
| **Pager Atomic** | `src/debug/test_pager_atomic.py` | **ACTIVE** | [FEAT-298] Verifies BKM-022 atomic swap protocol for the UI forensic ledger. |
| **Recruiter Match** | `src/test_recruiter.py` | **STALE** | Verifies the nightly job-matching logic against the CV summary. |

---

## 🎙️ 8. Audio & Streaming (The Sensory Node)
Verifies the NeMo-based EarNode and real-time STT capabilities.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Audio Pipeline** | `src/test_audio_pipeline.py` | **ACTIVE** | Tests the Float32 -> Int16 conversion and STT streaming path. |
| **GUI Flows** | `src/debug/test_gui_flows.py` | **ACTIVE** | Verifies browser-to-server UI event handshakes. |
| **EarNode Isolated** | `src/test_earnode_isolated.py` | **GEM** | Verifies EarNode initialization and CUDA Graph behavior. |
| **Web Binary** | `src/debug/test_web_binary.py` | **STALE** | Tests the integrity of audio chunks sent via WebSocket binary frames. |

---

## 📡 9. The Scouts & Logic (New Nodes)
Extended capabilities for live research and structured thinking.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Browser Probe** | `src/test_browser_isolated.py` | **ACTIVE** | Verifies Playwright initialization in the Browser Node. |
| **Sequential Thinking**| `src/test_thinking_node.py` | **ACTIVE** | Verifies stateful multi-step reasoning chains. |

---

## 🏗️ 10. Scanner & Synthesis (Background Recovery)
Surgical tools for the Portfolio_Dev "Face" pipeline. Use these when the Slow Burn stalls or parity is lost.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Mass Scan Engine** | `Portfolio_Dev/field_notes/mass_scan.py` | **ACTIVE** | [P9] Continuous background scanner processing the 18-year archive. |
| **Site Synthesizer** | `Portfolio_Dev/field_notes/build_site.py` | **ACTIVE** | Compiles static search index and cache-busted HTML pages. |
| **Artifact Sync** | `src/bridge_burn_to_rag.py` | [NEW] Indexes the physical asset catalog (files.html) into RAG. |

---

## 🤖 11. Delegation & Swarm Orchestration (BKM-034)
Helper scripts and execution wrappers for delegating development stories to OpenAgent swarms on port 4096.

| **Delegation Launcher** | `src/tests/delegate.py` | **ACTIVE** | [BKM-034/BKM-042] [GOLD] Standard OpenAgent story dispatch harness via port 4097 REST API. Supports `--reference`, `--target`, `--mode`, and `--verification`. |
| **Live Lab Gauntlet** | `src/tests/run_live_lab_gauntlet.sh` | **ACTIVE** | [SPR-53.0] [GOLD] Unified non-mocked integration test runner calling live endpoints (`:8088`, `:8765`, `:9090`, `:11434`). |
| **Adapter Swap Test** | `src/tests/test_vllm_adapter_swap.py` | **ACTIVE** | [SPR-52.0] Verifies zero-downtime hot-reload contract for `cli_voice_v1` LoRA adapter on vLLM. |
| **Scratch Delegate** | `src/tests/scratch_delegate.py` | **LEGACY** | [BKM-034] Legacy CLI wrapper; replaced by REST API `delegate.py`. |
| **Nudge 2024** | `field_notes/nudge_2024.py` | [RECOVERY] Clears hash for 2024 files to force a targeted re-nibble. |
| **Clean Data** | `field_notes/clean_data.py` | **DANGER.** Wipes the data directory. |

---

## 🧬 12. Nightly Forge & Distillation Diagnostics (Sprint 58)
Diagnostic and shakedown instruments validating the production infrastructure (`src/infra/nightly_forge.py`, `refine_gem.py`, and `mass_scan.py`).

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Agentic-R Retrieval Test** | `src/tests/test_agentic_r_retrieval.py` | **ACTIVE** | [SPR-58.0] [GOLD] Unit test suite verifying Maximal Marginal Relevance (MMR) novelty re-ranking and Ripgrep autonomous search pivot. |
| **Forge Distillation Unit** | `src/tests/test_forge_distillation_unit.py` | **ACTIVE** | [SPR-58.0] [GOLD] Unit test suite verifying Tri-Field schema parsing, backward compatibility, code artifact Jeopardy pairs, and 590+ dataset integrity. |
| **Nightly Forge Shakedown** | `src/tests/test_nightly_forge_shakedown.py` | **ACTIVE** | [SPR-58.0] [GOLD] Full end-to-end integration shakedown verifying module imports, REST quiesce/re-ignite contracts, train_expert dataset mapping, and dreaming subprocess handling. |

---

## 🛰️ 13. Modular Satellite & Epistemic Instruments (Sprint 59)
Diagnostic and verification test suites validating the Sprint 59 Modular Satellite architecture, deterministic evaluation batteries, and live co-pilot feedback loops.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Sprint 59 Integration Suite** | `src/tests/test_sprint59_integration.py` | **ACTIVE** | [SPR-59.0] [GOLD] Full-loop integration test suite validating Fourth Wall critique interception, Floating Oracle candidate pool injection, live AST context compaction, and Epistemic evaluator consistency (4/4 tests). |
| **Universal Epistemic Evaluator** | `src/tests/test_binary_evaluator_unit.py` | **ACTIVE** | [SPR-59.0] [FEAT-454] Unit test suite verifying 0% score drift and deterministic Rank = min(5, 1+sum(bool)) across 5 boolean checks (31/31 tests). |
| **AST Context Compiler Unit** | `src/tests/test_context_compiler.py` | **ACTIVE** | [SPR-59.0] [FEAT-455] Unit test suite verifying AST symbol extraction, function body stripping, >50% token compaction, and cross-module dependency trees (22/22 tests). |
| **Fourth Wall Interceptor Unit** | `src/tests/test_feedback_interceptor.py` | **ACTIVE** | [SPR-59.0] [FEAT-456/BKM-035] Unit test suite verifying linguistic critique detection, BKM-022 atomic JSONL write, and in-character refinement prompt generation (30/30 tests). |
| **Floating Validation Oracle Unit** | `src/tests/test_floating_oracle.py` | **ACTIVE** | [SPR-59.0] [FEAT-458] Unit test suite verifying candidate harvesting, missing-file fallbacks, candidate pool formatting, and shallow turn classification (53/53 tests). |
| **Speculative Pre-fetch Unit** | `src/tests/test_interest_speculative_prefetch.py` | **ACTIVE** | [SPR-59.0] [FEAT-457] Unit test suite verifying Turn 1 background RAG pre-fetch and interest preemption (2/2 tests). |

---
**Standard Certification Runner**:
```bash
PYTHONPATH=. .venv/bin/pytest src/tests/test_sprint59_integration.py \
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
PYTHONPATH=. .venv/bin/pytest src/tests/test_override_parser.py \
                             src/tests/test_maintenance_sweeper.py \
                             src/tests/test_audio_pipeline.py \
                             src/tests/test_sprint60_integration.py
```

---

## 15. Sprint 71 Live Elapsed Telemetry & Silicon Stability Gauntlet (SPR-71.0)
Verification instruments validating `FEAT-265` mandatory blocking status timeout, `FEAT-525` Live Round Table elapsed time checkpoints, and non-mocked physical silicon deliberations.

| Tool | Path | V4 Status | Goal |
| :--- | :--- | :--- | :--- |
| **Live Elapsed Time UI** | `src/tests/test_benchmarks_elapsed_time_ui.py` | **ACTIVE** | [FEAT-525] [GOLD] Playwright DOM test validating the "LIVE ROUND TABLE ELAPSED TIME" tab, canvas dimensions, and expandable "LIVE ELAPSED CHECKPOINTS" ledger drawer. |
| **Sprint 71 Stability Gauntlet** | `src/tests/test_live_sprint71_stability.py` | **ACTIVE** | [FEAT-265/525] [GOLD] Live silicon test suite exercising fresh bytecode integrity, stale client commit rejection (WS 1008), dialogue roll-up, and full 5-stage Round Table deliberation timing. |

---
**Sprint 71 Certification Runner**:
```bash
PYTHONPATH=. .venv/bin/pytest src/tests/test_benchmarks_elapsed_time_ui.py \
                             src/tests/test_live_sprint71_stability.py -v
```

