# Acme Lab: Tool Rundown (v4.0.0)

This document provides a technical overview of every high-fidelity tool available across the Bicameral Mind following the **Phase 7 Restoration Sprint**.

## 🛡️ Base Capabilities (Inherited by all Nodes)
*Defined in `nodes/loader.py`. Every hemisphere supports these core functions.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `deep_think` | Executes complex reasoning tasks. | The primary engine for technical strategy and derivation. |
| `scribble_note` | Caches a response semantically. | [RE-FEAT-082] Persists turn-to-turn technical memory for future recall. |
| `bounce_node` | Triggers a local process restart. | [RE-FEAT-045] Forces a re-prime of the inference engine (Ollama/vLLM). |
| `ping_engine` | Generation Probe (Heartbeat). | [FEAT-192] Verifies and optionally forces engine readiness. |
| `reply_to_user` | Natural Language response. | Standardized bridge for model-to-human communication. |

---

## 📁 The Archives (archive_node.py)
*Primary duty: Ground truth retrieval, personal history, and system vitals.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `list_cabinet` | Scans `archive/`, `drafts/`, and `workspace/`. | Populates the UI Filing Cabinet with a navigable file tree. |
| `read_document` | Reads raw content from workspace or drafts. | Bridges physical archives to the active reasoning stream. |
| `get_context` | Multi-Stage Retrieval (RAG). | [FEAT-117] Discovered anchors in ChromaDB and retrieves raw JSON truth. |
| `peek_related_notes` | Searches the 18-year archive index. | Finds historical "BKMs" or "Scars" based on keywords. |
| `access_personal_history`| Recalls teaching moments. | [RE-FEAT-193] Connects to `learning_ledger.jsonl` for historical recall. |
| `build_cv_summary` | Bridge to 3x3 CVT context. | [RE-FEAT-194] Injects career strategy into the active session. |
| `get_lab_health` | Retrieves physical telemetry. | [FEAT-191] Real-time VRAM, Temp, and Power metrics from Attendant. |
| `vram_vibe_check` | Quick hardware vital check. | [FEAT-191] Rapid assessment of 2080 Ti headroom before heavy tasks. |
| `get_current_time` | Precision Temporal Sync. | Returns the current system time and date for grounding. |
| `create_event_for_learning`| The Pedagogue's Ledger. | Logs teaching moments or failures to the archive for evolution. |
| `get_stream_dump` | Retrieves full raw short-term memory. | Essential for mining session tasks and Interaction history. |
| `patch_file` | Unified Diff Applicator. | [BKM-012] Surgically updates workspace files with mandatory lint-gate. |
| `dream` | Memory Consolidation. | Synthesizes chaotic logs into "Diamond Wisdom" and purges source logs. |
| `internal_debate` | Multi-node peer review. | Initiates a "duel" between nodes to resolve technical risks. |

---

## 🧠 The Brain (brain_node.py)
*Primary duty: Sovereign reasoning and whiteboard collaboration.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `update_whiteboard` | Writes to `whiteboard.md`. | Provides a persistent view of sovereign architectural plans. |
| `wake_up` | Resonates the weights. | Keep-alive signal for the reasoning engine. |

---

## 🐹 Pinky (pinky_node.py)
*Primary duty: Triage, semantic intent, and intuition.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `facilitate` | Intuitive intent classification. | Determines domain (Telemetry vs. Architecture) for PMM routing. |
| `peek_strategic_map` | Views the Archive Topography. | [FEAT-181] Accesses `semantic_map.json` for global context. |
| `trigger_morning_briefing`| Semantically triggers news. | [FEAT-072] Briefs user on nightly activities based on intent "vibe". |
| `lab_shutdown` | The Curfew. | Gracefully terminates the Lab's active mind loop. |

---

## 📡 The Scouts & Logic (New Nodes)
*Extended capabilities for live research and structured thinking.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `browse_url` | The Scout's Eyes (browser_node.py). | High-fidelity headless browser for live web research. |
| `sequential_thinking` | The Logic Gate (thinking_node.py). | Forces multi-step, stateful reasoning for complex problems. |

---

## 📡 The Architect (architect_node.py)
*Primary duty: Protocol generation and semantic mapping.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `generate_bkm` | Creates authoritative BKMs. | Transforms technical derivations into standardized BKM Protocol docs. |
| `build_semantic_map` | Updates the Archive Topography. | [FEAT-037] Re-indexes the 18-year archive into clusters. |

---

## 🛠️ Development & Validation Utilities
*Low-level scripts for Lab maintenance and silicon verification.*

| Tool | Command / Flag | Purpose |
| :--- | :--- | :--- |
| `Hallway Protocol` | `mass_scan.py --keyword [K]` | [FEAT-179] Real-time "Deep Retrieval" for targeted technical gaps. |
| `Mass Scan` | `mass_scan.py` | Continuous refinement burn of the 18-year archive. |
| `Distill Forge` | `distill_gems.py` | [FEAT-161] Transforms Rank 4 gems into LoRA training pairs. |
| `Safe-Scalpel` | `debug/atomic_patcher.py` | Batch replacement with mandatory rollback on lint failure. |
| `Lab Attendant` | `lab_attendant.py` | [V2] REST (:9999) + Native MCP controller for silicon lifecycle. |
| `Smoke Gate` | `debug/smoke_gate.py` | Simple pass/fail full-stack initialization check. |
| `Lab Probe` | `debug/lab_probe.py` | Python-based Attendant controller for reliable boot wait. |
| `Pinky Ping` | `debug/pinky_ping.py` | WebSocket-based responsiveness verification for Pinky. |
| `Physician's Gauntlet`| `test_lifecycle_gauntlet.py` | Full-stack sanity check covering boot, reasoning, and shutdown. |
| `Live Fire Test` | `test_strategic_live_fire.py`| [FEAT-182] Validates end-to-end PMM routing on physical silicon. |
