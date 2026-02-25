# 🩺 Acme Lab: Diagnostic & Test Rundown [v4.0]
**"The Physician's Ledger"**

This document is the **Master Inventory** of all diagnostic instruments, test suites, and verification scripts within the Federated Lab. For a catalog of agentic capabilities and node-specific tools, see **[TOOL_RUNDOWN.md](./TOOL_RUNDOWN.md)**.

---

## 🏎️ 1. Silicon & VRAM (Hardware Profiling)
These tools verify that the Lab's weights fit within the 11GB VRAM budget and that high-throughput kernels (Liger) are active.

| Tool | Path | Goal |
| :--- | :--- | :--- |
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
| **Gauntlet** | `src/debug/test_lifecycle_gauntlet.py` | Stress tests the Hub with rapid connect/disconnect cycles. Essential for verifying `aiohttp` resilience. |
| **Attendant Sanity** | `src/debug/test_attendant_sanity.py` | Verifies the Lab Attendant's HTTP API (Start/Stop/Status/Wait_Ready). |
| **Shutdown Resilience**| `src/debug/test_shutdown_resilience.py`| Verifies that the Lab can shut down via native tool flow. |
| **Liveliness** | `src/test_liveliness.py` | Standard heartbeat check. Verifies the WebSocket port is open and the `READY` state is achievable. |
| **Shutdown Flow** | `src/test_shutdown.py` | Validates clean exit sequences and PID cleanup for all lab processes. |
| **Interrupt Test** | `src/test_interrupt.py` | Tests handling of SIGINT/KeyboardInterrupt across the multi-process stack. |

---

## 🎭 3. Persona & Banter (The "Soul")
Ensures the Lab maintains its Bicameral character without falling into "Chatter Traps" or repetitive loops.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Latency Tics** | `src/test_latency_tics.py` | Verifies that Pinky sends \"Thinking\" tics during long Brain reasoning cycles. |
| **Persona Audit** | `src/debug/test_persona_bugs.py` | Checks for verbosity issues and ensures \"Certainly!\" filler is stripped. |
| **Contextual Echo** | `src/debug/test_contextual_echo.py` | Verifies persona-aware echo behavior. |
| **MIB Wipe** | `src/debug/test_mib_wipe.py` | Verifies the \"Neuralyzer\" memory clearing mechanic and context cap. |
| **Banter Decay** | `src/debug/test_banter_decay.py`| Verifies that reflexes slow down correctly during idle states. |
| **Echo Check** | `src/test_echo.py` | Verifies basic text/binary processing in the \"Talk & Read\" loop. |
| **Intercom Flow** | `src/test_intercom_flow.py` | End-to-end test of the CLI `intercom.py` client communication. |

---

## 🧠 4. Bicameral Logic (Hemispheric Crosstalk)
Validates "Thought Partner" capabilities, including delegation, tool access, and directness.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Pi Flow** | `src/debug/test_pi_flow.py` | **CRITICAL.** Verifies the \"Direct Answer First\" rule. |
| **Iron Gate Audit** | `src/debug/gate_triage_audit.py`| Verifies the hardened gate for casual vs. strategic triage. |
| **Dispatch Logic** | `src/debug/test_dispatch_logic.py` | Verifies the hardened priority dispatcher and hallucination shunt. |
| **Round Table** | `src/test_round_table.py` | Validates the Pinky -> Brain handover logic and shared context persistence. |
| **Tool Registry** | `src/debug/test_tool_registry.py` | **CRITICAL.** Confirms all physical MCP tools are visible to the agentic layer. |
| **Strategic Sentinel**| `src/debug/test_strategic_sentinel.py`| Verifies Amygdala filtering and typing-aware reflex suppression. |
| **Resurrection Tools**| `src/debug/test_resurrection_tools.py`| Verifies high-value restored tools: CV Builder, BKM Generator, and History Access. |
| **Architect Flow** | `src/debug/test_architect_flow.py` | Validates the Architect Node's BKM synthesis logic. |
| **Draft Agency** | `src/test_draft_agency.py` | Tests the `write_draft` tool and the "Editor Cleaning" pattern. |
| **MCP Integration** | `src/test_mcp_integration.py` | Verifies low-level MCP server handshakes and tool discovery. |

---

## 💾 5. Data & Memory (The Archives)
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

## 🎙️ 6. Audio & Streaming (The Sensory Node)
Verifies the NeMo-based EarNode and real-time STT capabilities.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Audio Pipeline** | `src/test_audio_pipeline.py` | Tests the Float32 -> Int16 conversion and STT streaming path. |
| **GUI Flows** | `src/debug/test_gui_flows.py` | Verifies browser-to-server UI event handshakes. |
| **EarNode Isolated** | `src/test_earnode_isolated.py` | Verifies EarNode initialization and CUDA Graph behavior in isolation. |
| **Web Binary** | `src/debug/test_web_binary.py` | Tests the integrity of audio chunks sent via WebSocket binary frames. |

---

## 🔪 7. The Scalpels (Atomic Patching)
Scripts wrapping `atomic_patcher.py` for lint-verified, high-fidelity core changes.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Scalpel Persona** | `src/debug/run_scalpel_persona.py` | Batch refines system prompts for Pinky and Brain. |
| **Scalpel Lifecycle**| `src/debug/run_scalpel_lifecycle.py`| Fixes state machine bugs in `acme_lab.py`. |
| **Scalpel Warp** | `src/debug/run_scalpel_warp.py` | Fast-track path hardening for absolute utility resolution. |
| **Scalpel Core** | `src/debug/run_scalpel.py` | General-purpose atomic patching wrapper. |
| **Verify Sprint** | `src/debug/verify_sprint.py` | Aggregate script that runs a subset of tests to verify sprint goals. |

## 🧱 8. Resilience Ladder (Stability States)
These instruments verify the system's ability to degrade gracefully under hardware pressure.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Engine Swap** | `src/debug/test_engine_swap.py` | Verifies the hot-swap from vLLM to Ollama fallback. |
| **Downshift** | `src/debug/test_downshift_protocol.py`| Verifies transition from Gemma 2 2B to Llama-3.2-1B during multi-use peaks. |
| **VRAM Guard** | `src/test_vram_guard.py` | Validates the SIGTERM \"Deep Sleep\" suspension. |

---

## 🏗️ 9. Core Framework Audits
Low-level verification of underlying libraries and architectural constraints.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Forensic Logging** | `src/debug/test_forensic_logging.py`| Verifies the Montana Protocol and log rotation. |
| **aiohttp Stability** | `src/debug/test_aiohttp.py` | Verifies WebSocket handshake resilience and async loop stability. |

---

## 🛡️ 10. The Physician's Gauntlet (Deep Hardening)
High-fidelity behavioral verification of cognitive and systemic integrity.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Grounding Fidelity** | `src/debug/test_grounding_fidelity.py` | Verifies Brain responses use ONLY provided historical anchors. |
| **Consensus Loop** | `src/debug/test_consensus_loop.py` | Validates synthesis quality of the Internal Debate peer-review. |
| **Deep Smoke** | `acme_lab.py --mode DEEP_SMOKE` | State-machine validation: Ingest -> Reason -> Dream -> Recall. |

---
**Usage**: Before concluding any session, run `src/debug/test_lifecycle_gauntlet.py`, `src/debug/verify_sprint.py`, and the **Physician's Gauntlet** to ensure the core is still standing.
