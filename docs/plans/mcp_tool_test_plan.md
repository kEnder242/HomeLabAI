# MCP Tool Integration Test Plan
**Status:** ACTIVE (Feb 11, 2026)
**Owner:** Gemini CLI Agent

## 🎯 Objective
To verify that all MCP tools across the three primary residents (Archive, Pinky, Brain) are functional, stable, and correctly integrated into the Intercom server (`acme_lab.py`).

## 🧱 Scope
This plan covers the live verification of tools within the managed `lab-attendant` environment.

### 1. Archive Node (The Filing Cabinet)
*   **Tool: `list_cabinet`**
    *   **Verify**: Returns a valid JSON structure of the `archive/`, `drafts/`, and `workspace/` directories.
*   **Tool: `read_document`**
    *   **Verify**: Can successfully read a file from the permitted paths (e.g., `archive/2024.json`).
*   **Tool: `peek_related_notes`**
    *   **Verify**: Can perform breadcrumb lookups through the `search_index.json`.

### 2. Pinky Node (The Gateway)
*   **Tool: `facilitate`**
    *   **Verify**: Correctly triages user queries into `reply_to_user` or `ask_brain`/`query_brain` JSON responses.
    *   **Verify**: Handles the "Lobby" state vs. "READY" state correctly.

### 3. Brain Node (The Mastermind)
*   **Tool: `deep_think`**
    *   **Verify**: Connects to the primary reasoning model (Windows Ollama) and returns grounded technical responses.
    *   **Verify**: Respects the `BRAIN_SYSTEM_PROMPT` grounding rules.
*   **Tool: `write_draft`**
    *   **Verify**: Can write a formatted `.md` or `.json` file to the `~/AcmeLab/drafts/` directory.
*   **Tool: `update_whiteboard`**
    *   **Verify**: Updates the persistent `whiteboard.md` file.

## 🧪 Execution Strategy
1.  **Automation**: Expand `HomeLabAI/src/test_all_tools.py` into `HomeLabAI/src/test_mcp_integration.py`.
2.  **Protocol**: Tests must be executed from the `Dev_Lab` root with correct `PYTHONPATH`.
3.  **Environment**: Require a live `lab-attendant` service with all residents sequentialy initialized.

## 🏁 Verification Cycle
*   **Pre-test**: `nvidia-smi` and `lab-attendant` status check.
*   **Test Run**: Execute `pytest HomeLabAI/src/test_mcp_integration.py`.
*   **Reporting**: Results logged to the system pager and integrated into the next Retrospective.
