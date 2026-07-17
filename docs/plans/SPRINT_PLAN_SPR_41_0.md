# Sprint 41 – Context Hardening & Tool-Driven Memory Realignment

This sprint focuses on resolving system persona leakage and context starvation in the waterfall reasoning flow by enabling local tool-calling for the remote reasoner, hardening the bedrock context, and transitioning the legacy whiteboard system to a structured, click-to-open Tool Log archive aligned with our Visibility BKM.

---

## 🛠️ One-Liner Prep & Installation
Before executing the stories, ensure you are in the correct python virtual environment and verify current git baselines:
```bash
# Verify submodules are clean and run test compile sweeps
cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/python3 -m py_compile src/logic/cognitive_hub.py src/nodes/loader.py
```

---

## Active Stories & Task Ledger

### Story 1: Tool-Driven Waterfall Cascade [HomeLabAI]
*   **Why**: Deep Thought and the Brain are currently called with `tools=[]` during the cascade, leaving them context-starved on specific queries and causing fallback hallucinations.
*   **Critical Logic & Line Pointers**:
    *   Target: `_run_brain_leg` in [cognitive_hub.py:L895-L914](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L895-L914)
    *   Instead of hardcoding `tools=[]`, retrieve the active tools from the node object using `self.residents["thought"].mcp.list_tools()` or mapping them dynamically.
*   **Scars & Failures to Avoid**:
    *   **The standard loop crash:** Ensure that tools are passed in the format expected by the MCP tool invocation payload (JSON-RPC list) to prevent vLLM API serialization errors.
*   **Verification Gate**:
    ```bash
    # Test query injection
    curl -X POST -H "Content-Type: application/json" -d '{"query": "IIRC it was BMC as a Validation Engine. Can you comment on your historical synthesis?"}' http://localhost:8765/inject
    
    # Audit log trace to verify tool call attempts
    tail -n 25 /home/jallred/Dev_Lab/HomeLabAI/logs/evaluation_batch_*.log
    ```

---

### Story 2: Context Starvation Protocol [HomeLabAI]
*   **Why**: Prevent models from hallucinating context when they lack the necessary tools or have empty retrieval inputs.
*   **Critical Logic & Line Pointers**:
    *   Target: `self.IDENTITY_BEDROCK` in [loader.py:L75-L82](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py#L75-L82)
    *   Append this rule:
        > `"CONTEXT_VALIDITY: If you are asked to analyze, summarize, or reference a specific historical topic or GEM ID, but the provided context is thin/empty and you have no active tools to retrieve evidence, you are FORBIDDEN from generating placeholder facts. You must output the exact token: [ERROR: CONTEXT_STARVED]."`
    *   Target: `_process_node_stream` in [cognitive_hub.py:L359-L370](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L359-L370)
    *   Detect if the generated output contains `[ERROR: CONTEXT_STARVED]`. If found, bypass the cascade and alert Foyer.
*   **Scars & Failures to Avoid**:
    *   **Attention Drift:** Ensure the starvation rule is appended as a high-authority system block. Do not put negative prompts (e.g. "Do not say X") as they trigger small models to print them. Use the explicit positive token trigger `[ERROR: CONTEXT_STARVED]`.
*   **Verification Gate**:
    ```bash
    # Inject unknown topic query with tools disabled
    curl -X POST -H "Content-Type: application/json" -d '{"query": "Provide a historical synthesis of the unregistered project GEM-9999"}' http://localhost:8765/inject
    
    # Assert that the output log captures the starvation token
    grep -q "CONTEXT_STARVED" /home/jallred/Dev_Lab/HomeLabAI/logs/evaluation_batch_*.log && echo "Pass" || echo "Fail"
    ```

---

### Story 3: Vibe-Specific Context Isolation [HomeLabAI]
*   **Why**: Rather than muting the model's persona, we enforce positive, tag-delimited grounding specifically during `HISTORICAL` and `FORENSIC` turns. This prevents bedrock details from bleeding into past-tense briefs, while preserving the model's ability to discuss operational metadata during `META` or `OPERATIONAL` turns.
*   **Critical Logic & Line Pointers**:
    *   Target: `_process_node_stream` in [cognitive_hub.py:L311-L320](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L311-L320)
    *   Wrap RAG context in `<historical_record>...</historical_record>` tags when the vibe is `HISTORICAL` or `FORENSIC`.
    *   Inject the positive grounding instruction to behavioral guidance:
        > `"GROUNDING_PROTOCOL: Formulate your response EXCLUSIVELY from the evidence provided inside the <historical_record> tags. Focus your analysis solely on the target events, dates, and validation systems described within these tags."`
*   **Scars & Failures to Avoid**:
    *   **The Forensic Leak:** Forensic queries target past trace files and can easily confuse the model into referencing current live system logs. Ensure `FORENSIC` receives the exact same `<historical_record>` boundary containment as `HISTORICAL`.
*   **Verification Gate**:
    ```bash
    # Inject historical query
    curl -X POST -H "Content-Type: application/json" -d '{"query": "historically, what do you know about 'Managability as a Validation Engine'?"}' http://localhost:8765/inject
    
    # Audit log trace to confirm that output contains no operational parameters (Z87-Linux, 2080 Ti)
    tail -n 30 logs/evaluation_batch_*.log
    ```

---

### Story 4: Table and Defeature Whiteboard System [HomeLabAI / Portfolio_Dev]
*   **Why**: The legacy whiteboard system (which syncs user edits and lets agents write to whiteboard.md) violates clean context flow, causes prompt contamination, and is prone to race conditions.
*   **Critical Logic & Line Pointers**:
    *   Target: `update_whiteboard` in [thought_node.py:L64-L73](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/thought_node.py#L64-L73) and `write_to_whiteboard` in [archive_node.py:L349-L358](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/archive_node.py#L349-L358).
    *   Target: [intercom_v2.js:L149-L152](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L149-L152) and the sidebar panel HTML in [lab.html:L118-L123](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/lab.html#L118-L123).
*   **Scars & Failures to Avoid**:
    *   **Unused Imports and Watchdogs:** Completely remove the test suites in `test_whiteboard_stability.py` to prevent background watcher scripts from raising missing file exceptions on startup.
*   **Verification Gate**:
    ```bash
    # Run test suite to verify whiteboard removal did not break general imports
    cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/python3 -m unittest discover -s src/tests/
    ```

---

### Story 5: Tool Log Archival Infrastructure [HomeLabAI / Portfolio_Dev]
*   **Why**: Replace the whiteboard notepad with an append-only Tool Log in the workspace that records all tool executions as clickable markdown links (`file:///...`), satisfying the Visibility BKM without chat flow pollution.
*   **Design**:
    *   The `tool_log.md` file will live in the workspace root. It is strictly an **archive** (context is passed "under the hood" via parameters, never read from `tool_log.md`).
*   **Critical Logic & Line Pointers**:
    *   Target: [loader.py:L504-L513](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/loader.py#L504-L513) (Telemetry/Broadcast setup).
    *   Write helper `append_to_tool_log` to write a markdown line:
        `- [time] [Node] called [Tool] with params [Params] -> Output stored at [Link](file://...)`
    *   Target: [intercom_v2.js](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js) WebSocket message handler.
    *   Render these events as collapsible details UI blocks.
*   **Verification Gate**:
    ```bash
    # Run query requiring tool calls
    curl -X POST -H "Content-Type: application/json" -d '{"query": "Can you retrieve the 2018 validation documents?"}' http://localhost:8765/inject
    
    # Assert tool_log.md is created and has links
    cat /home/jallred/Dev_Lab/HomeLabAI/tool_log.md
    ```
