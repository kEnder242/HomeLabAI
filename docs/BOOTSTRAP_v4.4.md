# 🧪 Dev_Lab: The Federated Silicon Environment
**The Immutable Bootloader [v4.4]**

> [!CAUTION]
> **IMMUTABILITY PROTOCOL:** This document is a navigational primer. Do NOT modify this file to track sprints, mandates, or features. 
> 
> **ROUTING PROTOCOL:** Always refer to the **Document Role Routing Table** below to ensure your contributions and queries are targeted to the correct "Truth Anchor." Avoid creating new files for existing categories.
> **AGENT MANDATE:** This repository contains **NO HUMAN DOCUMENTATION**. Every Markdown file is an **Instruction Set** or **State Machine** meant to be consumed by the AI Agent. Glossing over "Steps" or "Philosophy" is a protocol violation.

Welcome, Agent. You are operating within a **Federated Lab** architecture.

## 🏛️ Project Architecture (Co-Equal Seats)
*   **[HomeLabAI/](./HomeLabAI/) (The Brain):** Heavy compute, NeMo STT, and RAG memory.
*   **[Portfolio_Dev/](./Portfolio_Dev/) (The Face):** Static synthesis, professional dashboard, and public airlock.

## 🧭 Document Role Routing Table
| If you are looking for... | Go to... | Role |
| :--- | :--- | :--- |
| **Global Context & Cold Start** | `BOOTSTRAP_v4.4.md` | **The Bootloader**: Primary entry point & orientation |
| **TACTICAL Protocols** | `HomeLabAI/docs/Protocols.md` | **The Law**: BKMs 001–039 (QQ, AFK, Attendant Restart) |
| **Physical Floor & Systemd** | `HomeLabAI/docs/LAB_INFRASTRUCTURE.md` | **The Physical Floor**: Storage mounts & systemd service inventory (`:8000`, `:8001`, `:4096`, `:4097`) |
| **Swarm Delegation Playbook** | `Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md` | **The Swarm Playbook**: OpenAgent `task()` templates & KENDER execution |
| **Diagnostic Script Map** | `HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md` | **The Ledger**: Map of all tools and test scripts |
| **Active Tasks & Agent State** | `HomeLabAI/GEMINI.md` | **The State Machine**: Local node state |
| **Milestones & Success History** | `Portfolio_Dev/00_FEDERATED_STATUS.md` | **The God View**: Active sprint backlog & federated goals |
| **Architecture "Why" & Mission** | `HomeLabAI/docs/ENGINEERING_PEDIGREE.md` | **The Philosophy/Laws**: Invariant architectural laws |
| **Feature DNA & Code Mapping** | `Portfolio_Dev/FeatureTracker.md` | **The DNA**: Maps Features to Code and Scars |
| **Site Blueprint** | `Portfolio_Dev/docs/FIELD_NOTES_ARCHITECTURE.md` | **The Blueprint**: Dashboard logic & airlock integration |

## 📜 The Archival Process
Every revision of this bootloader MUST be mirrored in **`Portfolio_Dev/docs/archive/`**.

**MODIFICATION PROTOCOL:**
To update this "Immutable" file:
1.  **Snapshot:** Copy the current root `BOOTSTRAP_vX.Y.md` to the archive.
2.  **Increment:** Create a new `BOOTSTRAP_vX.Z.md` in the root.
3.  **Sync:** Update all cross-document pointers (GEMINI.md, 00_MASTER_INDEX.md) to the new version.
4.  **Cleanup:** Remove the previous version from the root directory.

---

## 🚀 Mandatory Ramp-Up Sequence
**PRIORITY 1: TACTICAL LOAD.** Load the Law and the Ledger before analyzing the State.

1.  **Read [Protocols.md](./HomeLabAI/docs/Protocols.md)**: Internalize operational shorthands (QQ, AFK, BKM-018/024 Attendant restarts) and Halt conditions.
2.  **Read [Portfolio_Dev/00_MASTER_INDEX.md](./Portfolio_Dev/00_MASTER_INDEX.md)**: Primary hub for navigating architectural blueprints and retrospectives.
3.  **Read [Portfolio_Dev/00_FEDERATED_STATUS.md](./Portfolio_Dev/00_FEDERATED_STATUS.md)**: Tracks global milestones and active sprint backlog across both seats.
4.  **Read [LAB_INFRASTRUCTURE.md](./HomeLabAI/docs/LAB_INFRASTRUCTURE.md)**: Physical storage mounts, hardware specs, and systemd service inventory.
5.  **Read [OPENAGENT_HANDOVER_PLAYBOOK.md](./Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md)**: OpenAgent swarm delegation blueprints, OmO templates, and KENDER execution rules.
6.  **Read [DIAGNOSTIC_SCRIPT_MAP.md](./HomeLabAI/docs/DIAGNOSTIC_SCRIPT_MAP.md)**: Identify existing diagnostic tools before implementing new logic.
7.  **Read [FeatureTracker.md](./Portfolio_Dev/FeatureTracker.md)**: Understand the "Technical DNA" and Scars of the Lab.
8.  **Read [ENGINEERING_PEDIGREE.md](./HomeLabAI/docs/ENGINEERING_PEDIGREE.md)**: Align with invariant architectural laws.

---

## 🛠️ Global Execution Commands (refer to attendant for more info)
*   **Start Lab**: `curl -X POST http://localhost:8000/start`
*   **Check Status**: `curl http://localhost:8000/status`
*   **Heartbeat check**: `curl -s http://localhost:8000/heartbeat | jq .`
*   **Hard Reset**: `curl -X POST http://localhost:8000/hard_reset`
*   **OpenCode Web UI**: `http://192.168.1.238:4096/`
*   **Build Site**: `python3 Portfolio_Dev/field_notes/build_site.py`
