# Acme Lab: Tool Rundown (v3.7.0)

This document provides a technical overview of every high-fidelity tool available across the Bicameral Mind.

## 📁 The Archives (archive_node.py)
*Primary duty: Ground truth retrieval and session persistence.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `list_cabinet` | Scans `archive/`, `drafts/`, and `workspace/`. | Populates the UI Filing Cabinet with a navigable file tree. |
| `read_document` | Reads raw content from workspace or drafts. | Bridges the physical disk to the AI and UI editor. |
| `peek_related_notes` | Searches the 18-year archive index. | Finds historical "BKMs" or "Scars" based on keywords. |
| `get_current_time` | Precision Temporal Sync. | Returns the current system time and date for grounding. |
| `create_event_for_learning`| The Pedagogue's Ledger. | Logs teaching moments or failures to the archive for evolution. |
| `get_stream_dump` | Retrieves full raw short-term memory. | Essential for mining session tasks and Interaction history. |

---

## 🧠 The Brain (brain_node.py)
*Primary duty: Deep reasoning, architectural synthesis, and drafting.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `update_whiteboard` | Writes to the shared `whiteboard.md` file. | Provides a persistent, live view of the Brain's reasoning. |
| `deep_think` | Executes complex reasoning tasks with context. | The core engine for technical strategy and coding. |
| `wake_up` | Resonates the weights. | Keep-alive signal for the reasoning engine. |

---

## 🐹 Pinky (pinky_node.py)
*Primary duty: Triage, hardware monitoring, and terminal gateway.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `facilitate` | Main loop router with "Temporal Moat" logic. | Decides whether to reply locally or delegate to the Brain. |
| `vram_vibe_check` | Retrieves real-time GPU VRAM stats. | Crucial for preventing OOM crashes on the 2080 Ti. |
| `get_lab_health` | Reports thermal and power draw via DCGM. | High-fidelity hardware diagnostics. |
| `get_my_tools` | The Map of the Mind. | Lists available tools to prevent agent hallucinations. |
| `lab_shutdown` | The Curfew. | Gracefully terminates the Lab's active mind loop. |

---

## 📡 The Scouts & Logic (New Nodes)
*Extended capabilities for live research and structured thinking.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `browse_url` | The Scout's Eyes (browser_node.py). | High-fidelity headless browser for live web research. |
| `sequential_thinking` | The Logic Gate (thinking_node.py). | Forces multi-step, stateful reasoning for complex problems. |

---

## 🛠️ Development & Validation Utilities
*Low-level utilities for Lab maintenance and silicon verification.*

| Tool | Path | Purpose |
| :--- | :--- | :--- |
| `Safe-Scalpel` | `debug/atomic_patcher.py` | Batch replacement with mandatory rollback on lint failure. |
| `Lab Attendant` | `lab_attendant.py` | Immutable bootloader for silicon and process lifecycle. |
| `Smoke Gate` | `debug/smoke_gate.py` | Simple pass/fail full-stack initialization check. |
| `Lab Probe` | `debug/lab_probe.py` | Python-based Attendant controller for reliable boot wait. |
| `Pinky Ping` | `debug/pinky_ping.py` | WebSocket-based responsiveness verification for Pinky. |
