# Diagnostic Script Map: The Physician's Ledger
**Role: [LEDGER] - Instrument Inventory**

> [!IMPORTANT]
> **PURPOSE:** A mapping of every physical script, test, and verification tool.
> **Tags**: [WD] Watchdog Logic | [PING] Health Probe | [SMOKE] Validation Cycle.

---

## 🏎️ 1. Silicon & VRAM (Hardware Profiling)
These tools verify that the Lab's weights fit within the 11GB VRAM budget and that high-throughput kernels (Liger) are active.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Hardware Grounding**| `src/tests/test_hardware_grounding.py`| [PHASE 7] Verifies real-time telemetry tools (`get_lab_health`) and engine priming. |
| **Engine Swap** | `src/debug/test_engine_swap.py` | Verifies the hot-swap from vLLM to Ollama fallback during moderate VRAM pressure. |
| **Apollo 11** | `src/debug/test_apollo_vram.py` | **CRITICAL.** Profiles active inference peak. Runs "Token Burn" to allocate KV cache and verify headroom. |
| **VRAM Guard** | `src/test_vram_guard.py` | Validates the "Stub" fallback logic when VRAM is >95% or engines fail to load. |
| **SIGTERM Protocol** | `src/debug/test_sigterm_protocol.py` | Verifies dynamic pre-emption and the flexible SIGTERM sequence for non-AI task priority. |
| **Liger Test** | `src/test_liger.py` | Specifically verifies that Liger-Kernels are accelerating the vLLM engine without crashing. |
| **VLLM Alpha** | `src/debug/test_vllm_alpha.py` | Low-level connectivity check for the vLLM OpenAI-compatible endpoint. |
| **MPS Stress** | `src/debug/mps_stress.py` | Legacy stress test for MPS (Metal) performance; maintained for cross-platform baseline. |
| **Liger Memory** | `test_liger_memory.py` | Compares VRAM footprint of Qwen2.5 with and without Liger Fused Kernels. |
| **MoE Load** | `test_moe_infinity.py` | Verifies the MoE-Infinity offloading engine using Mixtral-8x7B on SSD. |

---

## 🏗️ 2. Lifecycle & Orchestration (The Attendant)
These tools verify the `systemd` managed infrastructure and the Hub's resilience to state transitions.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Live Fire Triage**| `src/debug/test_live_fire_triage.py`| [PHASE 7][FEAT-199] **Active Auditor.** Rapid verification of parallel turn-bundling and hybrid (Pipe/JSON) triage. |
| **JSON Fix Experiment**| `src/debug/experiment_json_fix.py`| [DEBUG][FEAT-199] Standalone testbed for the Nuclear JSON extraction regex patterns. |
| **Strategic Live Fire**| `src/tests/test_strategic_live_fire.py`| [PHASE 7] **DEFINITIVE.** End-to-end physical hardware validation of the PMM routing and fidelity lifecycle. |
| **The Assassin** | `lab_attendant.py` (Internal) | [FEAT-119][WD] Atomic port-reaping using `fuser -k` before boot. |
| **Ghost Hunter** | `lab_attendant.py` (Internal) | [FEAT-121][WD] PGID-aware tree termination using `os.killpg()`. |
| **Gauntlet** | `src/debug/test_lifecycle_gauntlet.py` | Stress tests the Hub with rapid connect/disconnect cycles. Essential for verifying `aiohttp` resilience. |
| **Goodnight Bounce**| `src/debug/test_goodnight_bounce.py`| [FEAT-149][WD] Verifies appliance-grade resilience and auto-restart loop using Trace Monitoring. |
| **Attendant Sanity** | `src/debug/test_attendant_sanity.py` | [WD] Verifies the Lab Attendant's HTTP API (Start/Stop/Status/Wait_Ready). |
| **Shutdown Resilience**| `src/debug/test_shutdown_resilience.py`| Verifies that the Lab can shut down via native tool flow. |
| **Liveliness** | `src/test_liveliness.py` | Standard heartbeat check. Verifies the WebSocket port is open and the `READY` state is achievable. |
| **Shutdown Flow** | `src/test_shutdown.py` | Validates clean exit sequences and PID cleanup for all lab processes. |
| **Interrupt Test** | `src/test_interrupt.py` | Tests handling of SIGINT/KeyboardInterrupt across the multi-process stack. |

---

## 🎭 3. Persona & Banter (The "Soul")
Ensures the Lab maintains its Bicameral character without falling into "Chatter Traps" or repetitive loops.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Morning Briefing** | `src/tests/test_vibe_triggers.py` | [PHASE 7] Verifies semantic trigger for news/updates based on intent vibe (No hard-coded keywords). |
| **Latency Tics** | `src/test_latency_tics.py` | Verifies that Pinky sends \"Thinking\" tics during long Brain reasoning cycles. |
| **Persona Audit** | `src/debug/test_persona_bugs.py` | Checks for verbosity issues and ensures \"Certainly!\" filler is stripped. |
| **Contextual Echo** | `src/debug/test_contextual_echo.py` | Verifies persona-aware echo behavior. |
| **MIB Wipe** | `src/debug/test_mib_wipe.py` | Verifies the \"Neuralyzer\" memory clearing mechanic and context cap. |
| **Banter Decay** | `src/debug/test_banter_decay.py`| Verifies that reflexes slow down correctly during idle states. |
| **Neural Probe** | `src/debug/probe_hub.py` | [PING] **Bicameral Auditor.** Sniffs internal Hub hints (Exit Sentiment, Strategic Intent) and verifies bundled turn execution. |
| **Echo Check** | `src/test_echo.py` | Verifies basic text/binary processing in the \"Talk & Read\" loop. |
| **Intercom Flow** | `src/test_intercom_flow.py` | End-to-end test of the CLI `intercom.py` client communication. |

---

## 🧠 4. Bicameral Logic (Hemispheric Crosstalk)
Validates "Thought Partner" capabilities, including delegation, tool access, and directness.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Agentic Backtrack** | `src/tests/test_agentic_backtrack.py` | [PHASE 7] Verifies the Hallway Protocol and Strategic Pivot logic for Agentic-R. |
| **Pi Flow** | `src/debug/test_pi_flow.py` | **CRITICAL.** Verifies the \"Direct Answer First\" rule. |
| **Ghost Tool Sentry** | `src/tests/test_tool_validation.py` | [PHASE 7] Verifies detection and shunting of hallucinated tools back to Pinky. |
| **Iron Gate Audit** | `src/debug/gate_triage_audit.py`| **STALE.** Verifies the hardened gate for casual vs. strategic triage. (Requires audit for semantic intent). |
| **Dispatch Logic** | `src/debug/test_dispatch_logic.py` | Verifies the hardened priority dispatcher and hallucination shunt. |
| **Round Table** | `src/test_round_table.py` | Validates the Pinky -> Brain handover logic and shared context persistence. |
| **Tool Registry** | `src/debug/test_tool_registry.py` | [PING] **CRITICAL.** Confirms all physical MCP tools are visible to the agentic layer. |
| **Strategic Sentinel**| `src/debug/test_strategic_sentinel.py`| [PING] **STALE.** Verifies Amygdala filtering and typing-aware reflex suppression. (Requires audit). |
| **Resurrection Tools**| `src/debug/test_resurrection_tools.py`| Verifies high-value restored tools: CV Builder, BKM Generator, and History Access. |
| **Architect Flow** | `src/debug/test_architect_flow.py` | Validates the Architect Node's BKM synthesis logic. |
| **Draft Agency** | `src/test_draft_agency.py` | Tests the `write_draft` tool and the "Editor Cleaning" pattern. |
| **MCP Integration** | `src/test_mcp_integration.py` | Verifies low-level MCP server handshakes and tool discovery. |

---

## ⚒️ 5. The Forge (LoRA Synthesis)
Tools for distilling technical pedigree into specialized training data.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Deep-Connect Capture**| `src/forge/deep_connect_epoch_v2.py`| [PHASE 7][FEAT-202] **Stage 1 Capture.** Background harvest of raw technical blocks from the 18-year archive. |
| **Surgical Refinement**| `src/forge/refine_bones.py`| [PHASE 7][FEAT-202] **Stage 2 Refine.** Nuclear parsing pass to clean raw blocks into high-density BKM pairs. |
| **Distill Forge** | `src/forge/distill_gems.py` | [PHASE 8] Transforms Rank 4 gems into high-density LoRA training pairs. |
| **Expert Forge** | `src/train/train_expert.py` | [PHASE 8] Unsloth scaffolding for local 2080 Ti fine-tuning. |

---

## 💾 6. Data & Memory (The Archives)
Verifies the transition from raw logs to synthesized "Diamond" wisdom.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Dream Test** | `src/test_dream.py` | Validates the memory consolidation pipeline (`dream_cycle.py`). |
| **Memory Sync** | `src/test_memory_integration.py` | Verifies the end-to-end RAG path (ChromaDB + Embedding Server). |
| **Cache Check** | `src/test_cache_integration.py` | Verifies semantic cache lookups ("Consult Clipboard"). |
| **Dedup Check** | `src/test_dedup.py` | Validates semantic de-duplication of archived notes. |
| **Save Flow** | `src/test_save_flow.py` | Validates the "Strategic Vibe Check" triggered by manual file saves. |
| **Recruiter Match** | `src/test_recruiter.py` | Verifies the nightly job-matching logic against the CV summary. |

---

## 🎙️ 7. Audio & Streaming (The Sensory Node)
Verifies the NeMo-based EarNode and real-time STT capabilities.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Audio Pipeline** | `src/test_audio_pipeline.py` | Tests the Float32 -> Int16 conversion and STT streaming path. |
| **GUI Flows** | `src/debug/test_gui_flows.py` | Verifies browser-to-server UI event handshakes. |
| **EarNode Isolated** | `src/test_earnode_isolated.py` | Verifies EarNode initialization and CUDA Graph behavior in isolation. |
| **Web Binary** | `src/debug/test_web_binary.py` | Tests the integrity of audio chunks sent via WebSocket binary frames. |

---

## 📡 8. The Scouts & Logic (New Nodes)
Extended capabilities for live research and structured thinking.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Browser Probe** | `src/test_browser_isolated.py` | Verifies Playwright initialization in the Browser Node. |
| **Sequential Thinking**| `src/test_thinking_node.py` | Verifies stateful multi-step reasoning chains. |

---

## 🔪 9. The Scalpels (Atomic Patching)
Scripts wrapping `atomic_patcher.py` for lint-verified, high-fidelity core changes.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Scalpel Persona** | `src/debug/run_scalpel_persona.py` | Batch refines system prompts for Pinky and Brain. |
| **Scalpel Lifecycle**| `src/debug/run_scalpel_lifecycle.py`| Fixes state machine bugs in `acme_lab.py`. |
| **Scalpel Warp** | `src/debug/run_scalpel_warp.py` | Fast-track path hardening for absolute utility resolution. |
| **Scalpel Core** | `src/debug/run_scalpel.py` | General-purpose atomic patching wrapper. |
| **Verify Sprint** | `src/debug/verify_sprint.py` | Aggregate script that runs a subset of tests to verify sprint goals. |

---

## 🧱 10. Resilience Ladder (Stability States)
These instruments verify the system's ability to degrade gracefully under hardware pressure.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Engine Swap** | `src/debug/test_engine_swap.py` | Verifies the hot-swap from vLLM to Ollama fallback. |
| **Downshift** | `src/debug/test_downshift_protocol.py`| Verifies transition from Gemma 2 2B to Llama-3.2-1B during multi-use peaks. |
| **VRAM Guard** | `src/test_vram_guard.py` | Validates the SIGTERM \"Deep Sleep\" suspension. |

---

## 🛡️ 11. The Physician's Gauntlet (Deep Hardening)
High-fidelity behavioral verification of cognitive and systemic integrity.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Grounding Fidelity** | `src/debug/test_grounding_fidelity.py` | Verifies Brain responses use ONLY provided historical anchors. |
| **Consensus Loop** | `src/debug/test_consensus_loop.py` | Validates synthesis quality of the Internal Debate peer-review. |
| **Stability Marathon**| `src/debug/stability_marathon_v2.py` | Long-running stress test for 11GB VRAM fragmentation. |
| **Deep Smoke** | `acme_lab.py --mode DEEP_SMOKE` | [SMOKE] State-machine validation: Ingest -> Reason -> Dream -> Recall. |
| **Smoke Verify** | `src/debug/smoke_verify.py` | [SMOKE] Rapid verification of the Deep Smoke results in the archive. |

---

## 🏗️ 12. Scanner & Synthesis (Background Recovery)
Surgical tools for the Portfolio_Dev "Face" pipeline. Use these when the Slow Burn stalls or parity is lost.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Hallway Protocol** | `mass_scan.py --keyword [K]` | [PHASE 7] Real-time \"Deep Retrieval\" for targeted technical gaps. |
| **Nudge 2024** | `field_notes/nudge_2024.py` | [RECOVERY] Clears hash for 2024 files to force a targeted re-nibble. |
| **Force Feed** | `field_notes/force_feed.py` | [EMERGENCY] Bypasses mutex/load checks to jam a specific file into the engine. |
| **Librarian Debug** | `field_notes/test_chunking.py` | Verifies file splitting/classification logic before it hits the queue. |
| **Path Probe** | `field_notes/debug_2024.py` | Verifies absolute path resolution for the 2024 technical notes. |
| **Clean Data** | `field_notes/clean_data.py` | **NUCLEAR.** Wipes the data directory. Use ONLY for total archive corruption. |

---
**Usage**: Before concluding any session, run `src/debug/test_lifecycle_gauntlet.py`, `src/debug/verify_sprint.py`, and the **Physician's Gauntlet** to ensure the core is still standing.
