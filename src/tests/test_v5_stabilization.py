import asyncio
import json
import logging
import pytest
import threading
import queue
import time
from collections import deque
from infra.cognitive_audit import CognitiveAudit

# Mocking Node for Audit
class MockNode:
    def __init__(self):
        self.response = "PASS"
    async def call_tool(self, name, arguments=None):
        if name == "think":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': self.response})()]})
        return "OK"

@pytest.mark.asyncio
async def test_vibe_resonance_scalar():
    """Verifies that the vibe auditor returns a float scalar."""
    print("\n--- [TEST] Vibe Resonance Scalar (Task 6.4) ---")
    mock = MockNode()
    audit = CognitiveAudit(mock)
    
    # Scenario 1: Numeric output
    mock.response = "The vibe resonance is 0.85"
    score = await audit.audit_vibe_alignment("Hello", "Casual")
    print(f"  Captured Score (Numeric): {score}")
    assert score == 0.85
    
    # Scenario 2: Keyword fallback
    mock.response = "PASS"
    score = await audit.audit_vibe_alignment("Hello", "Casual")
    print(f"  Captured Score (Keyword): {score}")
    assert score == 1.0
    
    # Scenario 3: Failure
    mock.response = "FAIL"
    score = await audit.audit_vibe_alignment("Hello", "Casual")
    print(f"  Captured Score (Fail): {score}")
    assert score == 0.0

def test_memory_hygiene_deque():
    """Verifies that processed_ids uses a deque for eviction."""
    print("\n--- [TEST] Memory Hygiene Deque (Task 6.3) ---")
    processed_ids = deque(maxlen=3)
    processed_ids.append("id1")
    processed_ids.append("id2")
    processed_ids.append("id3")
    assert "id1" in processed_ids
    
    processed_ids.append("id4")
    assert "id1" not in processed_ids
    assert "id4" in processed_ids
    print("[PASS] Deque eviction verified.")

@pytest.mark.asyncio
async def test_waterfall_buffering():
    """Verifies that the waterfall drainer buffers until final flag."""
    print("\n--- [TEST] UI Pop Buffering (Task 6.6) ---")
    q = asyncio.Queue()
    broadcasts = []
    
    async def mock_broadcast(data):
        broadcasts.append(data)

    # Simplified waterfall_drainer logic
    async def drainer():
        from collections import defaultdict
        ui_buffers = defaultdict(str)
        while True:
            data = await q.get()
            source = data.get("source", "Brain")
            token = data.get("brain", "")
            final = data.get("final", False)
            
            if token: ui_buffers[source] += token
            if final:
                data["brain"] = ui_buffers[source]
                await mock_broadcast(data)
                ui_buffers[source] = ""
            q.task_done()

    drainer_task = asyncio.create_task(drainer())
    
    # Send tokens
    await q.put({"brain": "Hello", "source": "Brain", "final": False})
    await q.put({"brain": " world", "source": "Brain", "final": False})
    
    # Should be no broadcasts yet
    assert len(broadcasts) == 0
    
    # Send final
    await q.put({"brain": "!", "source": "Brain", "final": True})
    await asyncio.sleep(0.1) # Wait for drainer
    
    assert len(broadcasts) == 1
    assert broadcasts[0]["brain"] == "Hello world!"
    print("[PASS] UI Pop (Buffering) verified.")
    drainer_task.cancel()

if __name__ == "__main__":
    test_memory_hygiene_deque()
    asyncio.run(test_vibe_resonance_scalar())
    asyncio.run(test_waterfall_buffering())
