# Acme Lab: The Round Table Architecture
**Date:** January 8, 2026
**Status:** Design Phase

## 1. Core Concept: The Agentic Facilitator
We are moving from a **Linear Pipeline** (`User -> Pinky -> Brain -> User`) to a **Conversational State Machine**.

**Pinky** is no longer just the "greeter." He is the **Chairman of the Board** (or the Dungeon Master).
*   He manages the "Floor" (who speaks).
*   He critiques the Brain's output.
*   He manages Lab resources (lobotomies/upgrades).
*   He decides when the conversation is over.

**The Brain** remains the **Specialist Node**. It provides raw intelligence but generally does not drive the flow unless yielded to.

**The Lab** is the **Physics Engine**. It handles the "Barge-In" signals, message routing, and model instantiation.

---

## 2. The "Round Table" Loop
The system runs effectively as an infinite game loop until Pinky yields to the user.

### The Loop Logic (Pseudo-Code)
```python
class AcmeLab:
    async def process_event(self, initial_trigger):
        lab_context = self.get_snapshot()
        current_trigger = initial_trigger
        
        while True:
            # 1. Check for Interrupts (Barge-In)
            if self.check_interrupt_signal():
                current_trigger = Event("User shouted 'Hold on!'")
                self.stop_current_audio()

            # 2. Pinky's Turn (The Inner Voice)
            # Pinky sees the context and decides the next move.
            decision = await self.pinky.decide(current_trigger, lab_context)

            # 3. Execution
            if decision.tool == "reply_to_user":
                await self.speak(decision.content)
                break # Exit loop, wait for mic input

            elif decision.tool == "delegate_to_brain":
                # Pinky wants the Brain to work
                brain_output = await self.brain.think(decision.content)
                # Loop continues! Pinky gets to review the output.
                current_trigger = Event(f"Brain said: {brain_output}")

            elif decision.tool == "critique_and_retry":
                # Pinky isn't happy with the Brain. Send it back.
                current_trigger = Event(f"Pinky Feedback: {decision.content}")
                # Next loop iteration, Pinky (or Brain directly) handles this.

            elif decision.tool == "manage_lab":
                # "Brain needs a lobotomy"
                await self.perform_surgery(decision.target, decision.action)
                current_trigger = Event(f"System: {decision.target} upgraded.")
```

---

## 3. Pinky's "Inner Voice" (Tools)
Pinky's System Prompt will be updated to enforce **Tool Usage** as the primary output method. He does not "speak" directly; he calls tools.

### A. `reply_to_user(text: str, mood: str)`
*   **Action:** Synthesize TTS and send text to client.
*   **Effect:** Ends the current processing loop. Opens the microphone for user input.

### B. `delegate_to_brain(instruction: str, context: str, visible_to_user: bool)`
*   **Action:** Sends a prompt to the Brain Node.
*   **Effect:** Returns the Brain's text output *back to Pinky* (not the user) as a new event.
*   **Use Case:** "Brain, write that Python script." or "Brain, fact-check this statement."

### C. `critique_brain(feedback: str, severity: str)`
*   **Action:** Feeds the Brain's previous output back into the Brain with specific instructions to fix it.
*   **Effect:** Returns the *revised* Brain output to Pinky.
*   **Use Case:** "Gee Brain, you forgot the imports! Try again."

### D. `manage_lab(component: str, action: str, parameters: dict)`
*   **Action:** Triggers system-level changes.
*   **Target Components:**
    *   `"BRAIN_MODEL"`: Actions `LOAD`, `UNLOAD`, `SWAP` (e.g., switch `llama3` to `codellama`).
    *   `"MEMORY"`: Actions `SEARCH`, `CLEAR_SHORT_TERM`.
*   **Use Case:** "This is a hard math problem. Lab, swap Brain to `mixtral:8x7b`."

---

## 4. The "Barge-In" (Interrupt) Architecture
To support "Hold on guys!", the Lab must run the Loop tasks as **Cancellable Async Tasks**.

1.  **The Ear is Independent:** `EarNode` runs in a separate process/thread and feeds a `Queue`.
2.  **The Watchdog:** A background task monitors the `EarQueue`.
3.  **The Cancellation:**
    *   If `EarQueue` detects significant speech while `Loop` is running:
        *   `LoopTask.cancel()` is called.
        *   TTS Output is silenced (`websocket.send("STOP_AUDIO")`).
        *   A new `Event("User Interrupted: [Transcription]")` is created.
        *   The Loop restarts with this new event.

---

## 5. Scenario Walkthroughs

### Scenario 1: The Code Review (Back & Forth)
1.  **User:** "Write a snake game in Python."
2.  **Pinky:** Calls `delegate_to_brain("Write a snake game")`.
3.  **Brain:** Returns code (Missing `pygame` import).
4.  **Pinky (Inner):** Analyzes code. Sees missing import.
5.  **Pinky:** Calls `critique_brain("You forgot to import pygame!")`.
6.  **Brain:** Returns fixed code.
7.  **Pinky:** Calls `reply_to_user("Here is the fixed code, Brain had a hiccup!")`.

### Scenario 2: The Interrupt
1.  **User:** "Explain Quantum Physics."
2.  **Pinky:** Calls `delegate_to_brain`.
3.  **Brain:** Starts generating a 5-paragraph essay...
4.  **Lab:** Starts TTS: "Quantum physics is..."
5.  **User:** "Wait, stop, just give me the summary."
6.  **Lab (Watchdog):** Detects "Wait, stop".
    *   Kills Brain generation.
    *   Kills TTS.
7.  **Pinky:** Receives `Event("User interrupted: Wait, stop, just give me the summary")`.
8.  **Pinky:** Calls `delegate_to_brain("Summarize previous topic in one sentence")`.
9.  **Brain:** "It's about probability."
10. **Pinky:** Calls `reply_to_user("Brain says: It's about probability.")`.

---

## 6. Implementation Roadmap

### Step 1: Lab Upgrade (The Bus)
*   Modify `AcmeLab` to handle the `while True` loop and context maintenance.
*   Implement `check_interrupt()` logic.

### Step 2: Pinky 2.0 (The Facilitator)
*   Update `pinky_node.py` system prompt to be tool-centric.
*   Implement the `PinkyTools` (Delegate, Reply, Manage).

### Step 3: Brain 2.0 (The Worker)
*   Ensure Brain accepts "System Critique" messages efficiently.

### Step 4: Integration Test
*   Run the "Snake Game" scenario and verify Pinky catches errors (simulated) or facilitates the flow.
