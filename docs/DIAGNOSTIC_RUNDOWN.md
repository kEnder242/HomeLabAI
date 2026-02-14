# 🩺 Acme Lab: Diagnostic & Test Rundown [v3.9]
**"The Physician's Ledger"**

This document serves as the primary map for all diagnostic instruments and test suites within the Federated Lab. Use this during a **Cold-Start** to verify hardware stability and persona grounding.

---

## 🏎️ 1. Silicon & VRAM (Hardware Profiling)
These tools verify that the Lab's weights fit within the 11GB VRAM budget and that high-throughput kernels (Liger) are active.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Apollo 11** | `src/debug/test_apollo_vram.py` | **CRITICAL.** Profiles active inference peak. Runs "Token Burn" to allocate KV cache and verify headroom. |
| **VRAM Guard** | `src/test_vram_guard.py` | Validates the "Stub" fallback logic when VRAM is >95% or engines fail to load. |
| **Liger Test** | `src/test_liger.py` | Specifically verifies that Liger-Kernels are accelerating the vLLM engine without crashing. |

---

## 🏗️ 2. Lifecycle & Orchestration (The Attendant)
These tools verify the `systemd` managed infrastructure and the Hub's resilience to network friction.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Gauntlet** | `src/debug/test_lifecycle_gauntlet.py` | Stress tests the Hub with rapid connect/disconnect cycles. Essential for verifying `aiohttp` resilience. |
| **Attendant Sanity** | `src/debug/test_attendant_sanity.py` | Verifies the Lab Attendant's HTTP API (Start/Stop/Status/Wait_Ready). |
| **Liveliness** | `src/test_liveliness.py` | Standard heartbeat check. Verifies the WebSocket port is open and the `READY` state is achievable. |

---

## 🎭 3. Persona & Banter (The "Soul")
These tools ensure the Lab maintains its Bicameral character without falling into "Chatter Traps" or repetitive loops.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Latency Tics** | `src/test_latency_tics.py` | Verifies that Pinky sends "Thinking" tics during long Brain reasoning cycles to provide user feedback. |
| **Persona Audit** | `src/debug/test_persona_bugs.py` | Checks for verbosity issues and ensures "Certainly!" filler is stripped from draft writes. |
| **Reflex Check** | `src/test_echo.py` | Verifies the "Talk & Read" loop and basic text/binary processing. |

---

## 🧠 4. Bicameral Logic (Hemispheric Crosstalk)
These tools validate the "Thought Partner" capabilities, including delegation and directness.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Pi Flow** | `src/debug/test_pi_flow.py` | **CRITICAL.** Verifies the "Direct Answer First" rule. (e.g., Numeric Pi result vs. verbose script description). |
| **Round Table** | `src/test_round_table.py` | Validates the Pinky -> Brain handover logic and ensuring shared context persists. |
| **Tool Registry** | `src/debug/test_tool_registry.py` | **CRITICAL.** Confirms that all physical MCP tools (Archive, Browser, etc.) are visible to the agentic layer. |
| **Draft Agency** | `src/test_draft_agency.py` | Specifically tests the `write_draft` tool and the "Editor Cleaning" pattern. |

---

## 💾 5. Data & Memory (The Archives)
These tools verify the transition from raw logs to synthesized "Diamond" wisdom.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Dream Test** | `src/test_dream.py` | Validates the memory consolidation pipeline (`dream_cycle.py`). |
| **Clipboard Check** | `src/test_cache_integration.py` | Verifies semantic cache lookups in ChromaDB ("Consult Clipboard"). |
| **Save Flow** | `src/test_save_flow.py` | Validates the "Strategic Vibe Check" triggered by manual file saves in the Workbench. |

---

## 🔪 6. The Scalpels (Atomic Patching)
These scripts wrap the `atomic_patcher.py` to perform lint-verified, high-fidelity changes to the core.

| Tool | Path | Goal |
| :--- | :--- | :--- |
| **Scalpel Persona** | `src/debug/run_scalpel_persona.py` | Batch refines system prompts for Pinky and Brain. |
| **Scalpel Lifecycle**| `src/debug/run_scalpel_lifecycle.py`| Fixes state machine bugs in `acme_lab.py`. |
| **Scalpel Warp** | `src/debug/run_scalpel_warp.py` | Fast-track path hardening for absolute utility resolution. |

---
**Usage**: Before concluding any session, run `src/debug/test_lifecycle_gauntlet.py` to ensure the core is still standing.
