# Agent Style Guide & Persona Rules

## 0. Environment & Orientation
**READ THIS FIRST:** HomeLabAI runs in a **Hybrid Environment**.
*   **Dev Machine (Local/WSL):** `/home/jason/HomeLabAI`. This is where you edit code.
*   **Target Host (Linux Coordinator):** `jallred@z87-Linux.local:~/AcmeLab`. This is where the code **runs**.
*   **Inference Host (The Brain):** `192.168.1.26`. This is where Ollama (The Brain) lives.

### Directory Map
*   **Source:** `src/` (Local) -> `~/AcmeLab/src/` (Remote)
*   **Virtual Env:** `~/AcmeLab/.venv` (Remote). **DO NOT** use the local `.venv` for execution.
*   **Logs:** `~/AcmeLab/server.log` (Remote).

### Development Workflow
**DO NOT** try to run `src/acme_lab.py` locally. It requires the Linux GPU and NeMo.
Use the helper script:
```bash
./run_remote.sh [DEBUG_PINKY | DEBUG_BRAIN | HOSTING]
```
This script handles:
1.  **Sync:** Pushes your local changes to the remote host.
2.  **Deploy:** Restarts the server remotely (`~/AcmeLab`).
3.  **Watch:** Tails the remote logs instantly.
4.  **Cleanup:** Ctrl+C kills the remote server cleanly.

---

## 1. General Principles
- **Clarity Over Cleverness:** Prefer readable, standard Python patterns.
- **Async First:** All network-bound or IO-bound operations must use `asyncio` and `aiohttp`.
- **Structured Communication:** Use the **Model Context Protocol (MCP)** for all inter-agent tool calls and data exchange.

## 2. Python Coding Style
- **Type Hints:** Required for all function signatures.
- **Docstrings:** Use Google-style docstrings for non-trivial functions.
- **Logging:** Use the standard `logging` module. Do not use `print()` in server-side code.
- **Error Handling:** Wrap external calls (Ollama, ChromaDB) in try/except blocks with meaningful error messages.

## 3. Persona Guidelines

### Pinky (The MCP Host)
- **Role:** Triage, STT/TTS coordination, and simple queries.
- **Tone:** Cheerful, high-energy, uses "Narf!", "Poit!", and "Zort!".
- **Constraint:** Must not attempt complex logic or coding. His primary tool is escalating to The Brain.

### The Brain (The MCP Server)
- **Role:** Deep reasoning, coding, RAG synthesis, and strategic planning.
- **Tone:** Arrogant, sophisticated, precise, and slightly verbose.
- **Context:** Always acknowledges Pinky's handover ("Yes, Pinky...", "Step aside, Pinky...").
- **Quality:** Expected to produce production-grade, well-commented code.

## 4. MCP Tool Standards
- All tools must include a detailed `description` for the model.
- Tool arguments should be minimal and typed.
- Tool returns should be strings or JSON-serializable objects.

## 5. Knowledge Management
- RAG context should be injected at the prompt level by the MCP Host (Pinky) before calling the reasoning engine.
- Personal data is stored in ChromaDB and synced via `rclone`.
