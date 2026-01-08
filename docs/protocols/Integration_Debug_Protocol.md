# Protocol: Integration Debugging (The "Handshake")

**Problem:** Previous debug sessions left the User feeling "disconnected" because the Agent (AI) would fire off a server, hang indefinitely, or kill it too fast, without a clear signal for the User to intervene.

**Goal:** restore the "Co-Pilot" feel.

## The Protocol

### 1. The Setup (Agent)
The Agent prepares the environment but **does not start the blocking process yet**.
*   "I have updated the code. I am ready to start the server."
*   "Command to be run: `nohup ... &`"

### 2. The Trigger (User)
The User gives the "Go Ahead" or "Ready" signal.

### 3. The Watcher (Agent)
The Agent starts the server in **Background Mode** and immediately starts a **Log Watcher**.
```bash
# Agent runs this:
./start_server_detached.sh
tail -f server.log | grep --line-buffered -E "USER|PINKY|BRAIN"
```
*   **Crucial:** The Agent uses a `timeout` or specific "Exit Pattern" on the tail command so it doesn't hang forever if the server crashes silently.

### 4. The Interaction (User)
The User performs the physical test (speaking into the mic).
*   The Agent **sees** the logs flowing in real-time (via the `tail` output).

### 5. The Handoff (Agent)
Once the Agent sees the success criteria (e.g., `[PINKY] Hello!`), the Agent **stops watching** and reports back.
*   "I saw the 'Hello' response. Test successful. Do you want to try a 'Brain' query?"

### 6. The Teardown
The Agent asks: "Should I keep the server running for your own play, or kill it to save GPU?"
