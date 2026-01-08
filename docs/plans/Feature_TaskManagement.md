# Feature Draft: Pinky as Task Manager & Critic (via MCP)

**Status:** Backlog / Concept
**Related to:** Items #12 (Foil), #13 (Tasks), #14 (God Mode)
**Architecture:** Model Context Protocol (MCP)

## Concept
Pinky evolves from a simple router into a **Stateful Orchestrator**. He manages the lifecycle of a user's request, critiques the results, and escalates when necessary. This is implemented using **MCP** to standardize how he talks to tools and other agents.

## The Architecture: Pinky as MCP Host

Pinky (the application) acts as the **MCP Host**. He connects to various **MCP Servers**:
1.  **The Brain MCP:** Exposes "Deep Reasoning" and "Coding" as tools.
2.  **Ollama Manager MCP:** Exposes `list_models`, `pull_model`, `delete_model`.
3.  **External API MCP (God Mode):** Exposes `ask_gpt4`, `ask_claude`.
4.  **Filesystem/Memory MCP:** Exposes `read_notes`, `save_memory`, `update_todo`.

## Workflows

### 1. The Critic Loop (Item #12)
*   **Trigger:** The Brain returns a code snippet or plan.
*   **Action:** Pinky (using his "Common Sense" system prompt) evaluates the output.
    *   *Pinky:* "Egad! That looks complicated. Does it handle the error case?"
*   **Outcome:** If unsatisfied, Pinky sends it back to The Brain *before* showing the user.

### 2. Task State Management (Item #13)
*   **Storage:** Pinky maintains a `tasks.json` (or SQL) state via a Storage MCP.
*   **States:** `PENDING`, `IN_PROGRESS` (Brain working), `REVIEW` (Pinky checking), `COMPLETE`.
*   **Benefit:** If the system crashes, Pinky remembers: "We were in the middle of writing that Snake game!"

### 3. God Mode Escalation (Item #14)
*   **Condition:**
    *   The Brain fails twice.
    *   The User explicitly asks ("Ask God").
*   **Action:** Pinky uses the **External API MCP**.
    *   *Pinky:* "The Brain is stuck in a loop! Calling the Big Guy upstairs!"
*   **Result:** High-quality output injected back into the local context.

## Why MCP?
*   **Decoupling:** We can swap "The Brain" from a Windows PC to a cloud server just by changing the MCP endpoint.
*   **Extensibility:** Adding "Google Calendar" later is just adding another MCP server.
