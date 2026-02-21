# 🧪 Dev_Lab: The Federated Silicon Environment
**The Immutable Bootloader [v4.3]**

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
| **Global Context & Cold Start** | `BOOTSTRAP.md` | **The Bootloader**: this file |
| **TACTICAL** | **Operational Protocols**| `Protocols.md` | **The Law**: BKM-001+ (QQ, AFK, Cold-Start). |
| **Diagnostic Rundown** | `DIAGNOSTIC_RUNDOWN.md` | **The Ledger**: Map of all tools and tests. |
| **Active Tasks & Agent State** | `GEMINI.md` | **The State Machine** |
| **Milestones & Success History** | `00_FEDERATED_STATUS.md` | **The God View**: Tasks and backlog are here |
| **Architecture "Why" & Mission** | `ENGINEERING_PEDIGREE.md`| **The Philosophy/Laws** |
| **Feature DNA & Code Mapping** | `FeatureTracker.md` | **The DNA**: Maps Features to Code and Scars. |
| **ARCHITECTURAL**| **Site Blueprint** | `FIELD_NOTES_ARCHITECTURE.md`| **The Blueprint for the website side of things**: Site logic & integration. |

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

1.  **Read [Protocols.md](./HomeLabAI/docs/Protocols.md)**: Internalize the operational shorthands (QQ, AFK) and Halt conditions.
2.  **Read [Portfolio_Dev/00_MASTER_INDEX.md](./Portfolio_Dev/00_MASTER_INDEX.md)**
    : This is your primary hub for navigating architectural blueprints and historical logs. **Check this file for recent session breadcrumbs and retrospectives.**
2.  **Read [Portfolio_Dev/00_FEDERATED_STATUS.md](./Portfolio_Dev/00_FEDERATED_STATUS.md)** 
    :This tracks global milestones across both projects. Ignore other status docs if they conflict.
3.  **Read [DIAGNOSTIC_RUNDOWN.md](./HomeLabAI/docs/DIAGNOSTIC_RUNDOWN.md)**: Identify existing tools before implementing new logic.
4.  **Read [FeatureTracker.md](./Portfolio_Dev/FeatureTracker.md)**: Understand the "Technical DNA" and Scars of the Lab.
5.  **Read [ENGINEERING_PEDIGREE.md](./HomeLabAI/docs/ENGINEERING_PEDIGREE.md)**: Align with the Invariant Laws.


---

## 🛠️ Global Execution Commands (refer to attendant for more info)
*   **Start Lab**: `curl -X POST http://localhost:9999/start`
*   **Check Status**: `curl http://localhost:9999/status`
*   **Heartbeat check**: `curl -s http://localhost:9999/heartbeat | jq .`
*   **Hard Reset**: `curl -X POST http://localhost:9999/hard_reset`
*   **Build Site**: `python3 Portfolio_Dev/field_notes/build_site.py`
