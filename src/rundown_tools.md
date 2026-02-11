# Acme Lab: Tool Rundown (v3.4.4)

This document provides a technical overview of every tool available across the Bicameral Mind.

## 📁 The Archives (archive_node.py)
*Primary duty: Ground truth retrieval and session persistence.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `list_cabinet` | Scans `archive/`, `drafts/`, and `workspace/`. | Populates the UI Filing Cabinet with a navigable file tree. |
| `read_document` | Reads raw content from workspace or drafts. | Bridges the physical disk to the AI and UI editor. |
| `get_history` | Retrieves interaction logs from ChromaDB. | Provides context for long-running, state-aware conversations. |
| `peek_related_notes` | Searches the 18-year archive index. | Finds historical "BKMs" or "Scars" based on keywords. |
| `get_context` | Performs vector search on consolidated wisdom. | Retrieves high-fidelity technical context for the Brain. |
| `save_interaction` | Appends user/AI turns to the short-term stream. | Ensures every session is recordable for the "Dream Cycle". |
| `get_lab_status` | Pings Prometheus/Grafana/Airlock endpoints. | Reports the reachability of the Lab's service stack. |

---

## 🧠 The Brain (brain_node.py)
*Primary duty: Deep reasoning, architectural synthesis, and drafting.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `write_draft` | Writes/Overwrites files in the `drafts/` folder. | Permanent storage for synthesized plans and BKMs. |
| `wake_up` | Sends a keep-alive request to Windows Ollama. | Reduces latency by priming the GPU before reasoning begins. |
| `switch_model` | Swaps the active reasoning model (e.g., Llama to Mixtral). | Allows for "High-Stake" vs. "Fast" reasoning modes. |
| `update_whiteboard` | Writes to the shared `whiteboard.md` file. | Provides a persistent, live view of the Brain's reasoning in the UI. |
| `deep_think` | Executes complex reasoning tasks with context. | The core engine for technical strategy and coding. |

---

## 🐹 Pinky (pinky_node.py)
*Primary duty: Triage, hardware monitoring, and terminal gateway.*

| Tool | Function | Purpose |
| :--- | :--- | :--- |
| `facilitate` | Main loop router with "Temporal Moat" logic. | Decides whether to reply locally or delegate to the Brain. |
| `vram_vibe_check` | Retrieves real-time GPU VRAM stats via DCGM. | Crucial for preventing OOM crashes on the 2080 Ti. |
| `get_lab_health` | Reports thermal and power draw via DCGM. | High-fidelity hardware diagnostics for "Silicon health." |
| `access_personal_history`| Gated bridge to the Archive Node. | Retrieves ground truth ONLY when a "Temporal Key" is present. |
| `start_draft` | Triggers a new synthesis session. | Maps high-level user goals to the Brain's drafting tools. |
| `refine_draft` | Iterates on the active whiteboard content. | Allows the user to polish AI drafts agentically. |
| `commit_to_archive` | Finalizes a draft and saves it to the cabinet. | The "Seal of Approval" tool for finished technical work. |
| `manage_lab` | Admin tool for 'lobotomizing' the Brain. | Self-healing tool to clear reasoning loops or hung context. |
