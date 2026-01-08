# Feature Draft: Interactive Multi-Agent "War Room"

**Status:** Backlog / Concept
**Related to:** Item #6 (Logging/Review)

## Concept
Transform the current sequential interaction (User -> Pinky -> Brain -> User) into a **real-time, event-driven chat room**. 

Instead of a black box where the user waits for the final answer, the user joins a session where Pinky and The Brain are active participants. The user can watch the internal logic unfold and **interject** at any moment.

## User Story
*   **As a:** User (Jason)
*   **I want to:** See Pinky formulating his request to The Brain and potentially stop him or correct him *before* The Brain starts working.
*   **So that:** I can guide the agents efficiently without waiting for a long "thinking" cycle to finish just to say "No, that's not what I meant."

## Technical Requirements

### 1. Asynchronous Event Loop
*   **Current:** `check_turn_end` blocks until the chain completes.
*   **Proposed:** Agents run as background tasks. They publish "events" (Thought, Message, Request) to a shared bus (WebSocket).
*   **Effect:** The User client receives "Pinky is typing..." or "Pinky says: 'I better ask the Brain!'" immediately.

### 2. "Barge-In" (Interruption)
*   If the user speaks (or types) while an agent is generating:
    *   The Audio Server detects voice activity.
    *   A "STOP" signal is sent to the active LLM generation.
    *   The context buffer is updated with the partial sentence (so the agent knows it was interrupted).
    *   The system listens to the new user input.

### 3. The "Chat Room" Interface
*   Upgrade `view_logs.py` or the Client to be a full TUI (Text User Interface).
*   Allow text input *alongside* voice input to inject commands into the stream.

### 4. Unified Tooling Architecture (The Pinky-Brain Interface)
*   **Concept:** Instead of parsing text triggers, agents use a **Structured Tool System**.
*   **Integration:**
    *   **Delegation:** `ask_brain(query="...")`
    *   **Admin:** `manage_model(action="pull", model="llama3:70b")` (See Item #10)
*   **Visibility:** Every Tool Call is an event in the War Room. The user sees:
    *   *Event:* `[Pinky] 🛠️ Tool Call: ask_brain`
    *   *Args:* `{"query": "Rust Snake Game"}`
    *   *Status:* `⏳ Waiting for Brain...`

## Proposed Flow
1.  **User:** "Help me code a snake game."
2.  **Pinky (Text Stream):** "Ooh! A game! I love games! But I don't know Python..."
3.  **Pinky (Text Stream):** "ASK_BRAIN: Python Snake Game."
4.  **User (Interjecting):** "Wait, do it in Rust!"
5.  **Pinky (Interrupts Handoff):** "Egad! He changed his mind! ASK_BRAIN: Rust Snake Game."
6.  **Brain:** "Very well. Rust is superior anyway..."
