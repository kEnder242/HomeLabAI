import asyncio
import json
import time
import logging
from unittest.mock import AsyncMock, MagicMock, patch

# Configure logging for forensic visibility
logging.basicConfig(level=logging.INFO)

# Note: Using absolute imports as per project convention in tests
from logic.cognitive_hub import CognitiveHub

async def test_relay_interest_buildup():
    """
    [Task 3.1/3.3] Prototype Test for Contextual Buildup & Interest loop.
    Verifies BKM-032 by showing the Wordy Output of the Hub's internal ledger.
    """
    print("\n--- [TASK 3.1] PROTOTYPE: INTEREST BUILDUP & WORKSPACE CACHE ---")
    
    # Mocking residents
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    
    brain = MagicMock()
    brain.call_tool = AsyncMock()
    
    thought = MagicMock()
    thought.call_tool = AsyncMock()
    
    archive = MagicMock()
    archive.call_tool = AsyncMock()
    
    residents = {
        "pinky": pinky, "brain": brain, "thought": thought, "archive": archive,
        "lab": MagicMock() # Sentinel
    }
    residents["lab"].call_tool = AsyncMock()
    
    broadcast = AsyncMock()
    sensory = MagicMock()
    thought_online = MagicMock(return_value=True)
    
    async def monitor_pass_through(coro):
        return await coro
    
    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=thought_online,
        trigger_morning_briefing=AsyncMock()
    )
    
    # [FIX] BKM-032: Mock the Auditor to prevent recursive retry loops in tests
    hub.auditor = MagicMock()
    hub.auditor.audit_technical_truth = AsyncMock(return_value=True)
    
    # helper to create mock response
    def mock_resp(text):
        m = MagicMock()
        m.content = [MagicMock(text=text)]
        return m

    # --- TURN 1: THE HOOK ---
    query_1 = "[ME] Tell me about the RAPL-Sim implementation."
    print(f"\n[TURN 1] Query: {query_1}")
    
    triage_1 = json.dumps({
        "importance": 0.8, "casual": 0.1, "intrigue": 0.9,
        "vibe": "TECHNICAL_RESEARCH", "intent": "RECALL",
        "addressed_to": "BRAIN", "hints": "RAPL power limiting simulation"
    })
    
    # Configure Mocks for Turn 1
    residents["lab"].call_tool.return_value = mock_resp(triage_1)
    archive.call_tool.return_value = mock_resp('{"text": "[ACQUISITION Source: 2024_02.json]: RAPL-Sim uses /dev/cpu/0/msr.", "sources": ["2024_02.json"]}')
    
    pinky.call_tool.return_value = mock_resp("<thought> The user is asking about RAPL-Sim. I will trigger research mode. </thought> Narf! I'm looking into the RAPL-Sim files for you.")
    brain.call_tool.return_value = mock_resp("<thought> RAPL requires MSR tools. </thought> Local intuition: We solved the energy overflow bug in Epoch 2.")
    thought.call_tool.return_value = mock_resp("Architect analysis: The implementation relies on MSR registers for high-fidelity telemetry.")

    await hub.process_query(query_1)
    print(f"  Resulting Interest: {hub.current_interest:.2f}")

    # --- TURN 2: THE FOLLOW-UP ---
    query_2 = "[ME] How did we solve the kernel update issue for it?"
    print(f"\n[TURN 2] Query: {query_2}")
    
    triage_2 = json.dumps({
        "importance": 0.9, "casual": 0.1, "intrigue": 0.95,
        "vibe": "TECHNICAL_RESEARCH", "intent": "FOLLOW_UP",
        "addressed_to": "THOUGHT", "hints": "Kernel 6.8 breakages and RAPL fixes"
    })
    
    # Configure Mocks for Turn 2
    residents["lab"].call_tool.return_value = mock_resp(triage_2)
    archive.call_tool.return_value = mock_resp("✅ Ledger entry created.") # For both RAG and Ledger tool calls
    
    pinky.call_tool.return_value = mock_resp("<thought> Cascading to Deep Thought. </thought> Poit! Deep Thought is waking up to look at the kernel logs.")
    brain.call_tool.return_value = mock_resp("<thought> Checking kernel headers. </thought> The Brain: Intuition suggests a missing header in the new kernel headers.")
    thought.call_tool.return_value = mock_resp("Deep Thought: We patched the RAPL-Sim driver to use the new MSR-safe kernel symbols introduced in 6.12.")

    await hub.process_query(query_2)
    print(f"  Interest loop sustained. Interest: {hub.current_interest:.2f}")
    
    # Verify that thought traces were captured
    print(f"  Captured traces: {list(hub.turn_thought_trace.keys())}")
    assert "pinky" in hub.turn_thought_trace or "brain" in hub.turn_thought_trace

    # --- BKM-032: WORDY OUTPUT AUDIT ---
    print("\n--- [BKM-032] CONVERSATION LEDGER (Wordy Output) ---")
    if not hub.round_table_memory:
        print("!!! ERROR: Ledger is empty. Hub failed to record turn summary. !!!")
    for i, turn in enumerate(hub.round_table_memory):
        print(f"\n[TURN {i+1} RECONSTRUCTION]:")
        # Print with indentation to show it's a block
        for line in turn.split("\n"):
            print(f"  {line}")
    
    print("\n✅ Prototype Verification: Multi-turn flow simulated.")

if __name__ == "__main__":
    asyncio.run(test_relay_interest_buildup())
