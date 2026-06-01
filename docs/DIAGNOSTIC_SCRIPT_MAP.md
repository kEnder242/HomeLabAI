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

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Artifact Sync** | `src/bridge_burn_to_rag.py` | [NEW] Indexes the physical asset catalog (files.html) into RAG. |
| **Hallway Protocol** | `mass_scan.py --keyword [K]` | Real-time "Deep Retrieval" for targeted technical gaps. |
| **Nudge 2024** | `field_notes/nudge_2024.py` | [RECOVERY] Clears hash for 2024 files to force a targeted re-nibble. |
| **Clean Data** | `field_notes/clean_data.py` | **DANGER.** Wipes the data directory. |

---
**Usage**: Before concluding any session, run `src/debug/gold_master_batch_runner.sh` to certify the baseline.
