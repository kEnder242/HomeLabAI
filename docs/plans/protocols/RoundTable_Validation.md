# Validation Plan: Acme Lab "Round Table" Architecture

**Status:** Draft
**Target:** Validate the transformation of Pinky into an Agentic Facilitator and the Lab into an Event-Driven State Machine.

---

## Phase 1: The Loop (Logic Layer)
**Goal:** Verify the conversational state machine, tool usage, and "Inner Voice" logic.
**Execution Mode:** Autonomous "Coffee Break" (Simulated Input).

### Infrastructure Prerequisites
1.  **Debug Stream:** `AcmeLab` must broadcast `{"type": "debug", "event": "..."}` messages via WebSocket. This allows the test script to "see" Pinky's internal thoughts (Tool Calls) without relying on TTS.
2.  **Mock Brain:** For logic testing, we will use a "Mock Brain" mode that returns fixed text instantly (or with a delay) to avoid wasting tokens/time on real inference during flow validation.

### Test Case 1.1: The Direct Reply (Baseline)
*   **Scenario:** User says "Hello."
*   **Flow:** User -> Lab -> Pinky(Context) -> Tool:`reply_to_user("Hi!")` -> Lab -> Client.
*   **Success Criteria:**
    *   Debug Stream shows `Pinky Decision: REPLY`.
    *   Client receives text "Hi!".
    *   Loop terminates after 1 iteration.

### Test Case 1.2: The Delegation (Handoff)
*   **Scenario:** User says "Calculate pi."
*   **Flow:**
    1.  User -> Lab -> Pinky.
    2.  Pinky Tool: `delegate_to_brain("Calculate pi")`.
    3.  Lab executes Brain Node (Mock).
    4.  Lab updates Context: `Last Speaker: Brain`.
    5.  Pinky Tool: `reply_to_user("Brain says 3.14")`.
*   **Success Criteria:**
    *   Debug Stream shows `Pinky Decision: DELEGATE`.
    *   Debug Stream shows `Brain Output: ...`.
    *   Debug Stream shows `Pinky Decision: REPLY`.

### Test Case 1.3: The Critique (Multi-Turn Internal Loop)
*   **Scenario:** User says "Write bad code." (Mock Brain is programmed to return "print('hello')" without context).
*   **Flow:**
    1.  Pinky delegates.
    2.  Brain returns "print('hello')".
    3.  Pinky Tool: `critique_brain("Too simple, add a loop.")`.
    4.  Lab re-prompts Brain.
    5.  Brain returns "for i in range(10): print('hello')".
    6.  Pinky Tool: `reply_to_user`.
*   **Success Criteria:**
    *   Debug Stream tracks the chain: `DELEGATE` -> `BRAIN_OUT` -> `CRITIQUE` -> `BRAIN_OUT` -> `REPLY`.

---

## Phase 2: The Interrupt (Physics Layer)
**Goal:** Verify asynchronous "Barge-In" capabilities.
**Execution Mode:** Interactive / Timing-Sensitive Scripting.

### Infrastructure Prerequisites
1.  **Cancellable Tasks:** The `process_query` loop must be wrapped in an `asyncio.Task` that checks for a `CancellationError`.
2.  **Simulated Barge-In:** The `sim_client.py` will be updated to send a "Signal" message (e.g., `{"type": "barge_in"}`) mid-stream.

### Test Case 2.1: Interrupting "The Thinker"
*   **Scenario:**
    1.  User asks "Write a novel."
    2.  Pinky delegates to Brain.
    3.  **Simulated Delay:** Brain takes 10 seconds (simulated).
    4.  **T+2s:** User sends `Barge-In` signal ("Wait, stop").
*   **Expected Behavior:**
    *   Lab log: `[INTERRUPT] Cancelling current task...`
    *   Brain Node: Receives SIGINT or Task Cancel.
    *   Pinky: Immediately invoked with `Context: User said "Wait, stop"`.
    *   Pinky Tool: `reply_to_user("Stopped.")`.
*   **Failure Mode:** Brain continues processing despite the signal (Zombie Process).

### Test Case 2.2: Interrupting "The Speaker"
*   **Scenario:**
    1.  Pinky sends a long response (via TTS).
    2.  User sends `Barge-In` signal.
*   **Expected Behavior:**
    *   Lab sends `{"type": "control", "command": "stop_audio"}` to Client.
    *   Pinky is invoked with new context.

---

## Validation Script (Draft Idea)
A new script `src/test_round_table.py` will be created to run Phase 1.

```python
# Pseudo-code for Autonomous Validator
async def run_test():
    async with connect_to_lab() as ws:
        # Test 1.2
        await ws.send("Calculate pi")
        
        events = []
        async for msg in ws:
            events.append(msg)
            if msg['type'] == 'final_response': break
            
        assert "DELEGATE" in events
        assert "REPLY" in events
        print("✅ Test 1.2 Passed")
```
