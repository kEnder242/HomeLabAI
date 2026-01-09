# Housekeeping Report & Analysis (Jan 7, 2026)

## 1. Cohesiveness Audit & Conflict Detection

**Conflict Detected:** *Monolith vs. MCP Architecture*
*   **Current State:** `audio_server.py` is becoming a monolith. It handles Audio, STT, RAG, Ollama Calls, and Pinky/Brain Logic all in one file.
*   **Future Goal:** The "Task Management" plan calls for a modular **MCP (Model Context Protocol)** architecture.
*   **Resolution:** We must stop adding features directly to `audio_server.py`. The next major technical step *must* be refactoring Pinky into an MCP Host, or we will create technical debt that makes "God Mode" and "Model Manager" very hard to implement cleanly.

**Clarification Needed:** *Pinky's Authority*
*   **Issue:** "Pinky Model Manager" says Pinky manages the Brain. "The Brain Persona" says Brain is the boss.
*   **Resolution:** Pinky is the *System Administrator* (has root/sudo). The Brain is the *Chief Scientist* (has the IQ). Pinky manages the *hardware/infrastructure*; Brain manages the *logic*.

## 2. Validation & Testing Strategy

We need specific tests for each feature type.

| Feature Category | Test Method | Automation Level |
| :--- | :--- | :--- |
| **Personality (Pinky/Brain)** | `behavior_test.py` (Text Injection) | **High** (CI/CD style) |
| **Voice/STT** | `sim_client.py` (Audio Injection) | **High** (Repeatable) |
| **Wake-on-LAN (WOL)** | Manual Hardware Verification | **None** (Requires User) |
| **God Mode (External API)** | Mock API Responses | **High** (Unit Tests) |
| **Model Manager** | Dry-Run Commands (Don't actually delete models) | **Medium** (Safe Mode) |

## 3. Proposed Master Backlog & Priorities

I have merged the Backburner and Backlog, estimated difficulty (Story Points 1-5), and identified Intervention requirements.

### Phase A: Architecture Refactor (The Foundation)
*   **[AUTO] [Diff: 5] Refactor to MCP:** Split `audio_server.py`. Create `PinkyMCPHost` and `BrainMCPServer`. *Prerequisite for almost everything else.*
*   **[AUTO] [Diff: 3] Unified Tooling:** Replace `ASK_BRAIN:` string parsing with structured MCP tool calls.

### Phase B: Core Features (The "Pinky" Suite)
*   **[AUTO] [Diff: 3] Pinky Model Manager:** Implement Ollama API tools (`pull`, `list`). Pinky can manage Windows models.
*   **[AUTO] [Diff: 2] God Mode:** Add `call_external_api` tool to Pinky's belt.
*   **[AUTO] [Diff: 4] Live Participation ("War Room"):** Upgrade the logging/viewing system to a proper Event Bus so you can see tool calls live.

### Phase C: Intelligence & Memory
*   **[AUTO] [Diff: 4] Tiered Memory:** Implement Session Summaries and CLaRa integration.
*   **[AUTO] [Diff: 3] Task State Manager:** Pinky tracks "ToDo" lists across sessions.

### Phase D: Hardware & Infrastructure (User Heavy)
*   **[USER] [Diff: 2] Smart Power (WOL):** Configure Windows BIOS/NIC. Test `wakeonlan`.
*   **[USER] [Diff: 3] Secure Remote Access:** VPN/Tailscale setup.
*   **[USER] [Diff: 2] Streaming Awareness:** Script to detect Windows processes.

## 4. Next Steps Recommendation

1.  **Approve this Plan:** If you agree with the "MCP First" approach.
2.  **Execute Phase A:** I can autonomously refactor `audio_server.py` into the MCP pattern during a long session.
