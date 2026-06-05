import asyncio
import json
import logging
import pytest
import os
import time
from collections import deque
from infra.cognitive_audit import CognitiveAudit

# Mock for Hub tests
class MockResident:
    def __init__(self, name):
        self.name = name
    async def call_tool(self, name, arguments=None):
        if name == "think":
            return type('obj', (object,), {'content': [type('obj', (object,), {'text': f"Summary from {self.name}"})()]})
        return "OK"

async def test_sovereign_brief_distillation():
    """Verifies Task 2.2: Context Precision."""
    from logic.cognitive_hub import CognitiveHub
    print("\n--- [TEST] Sovereign Brief Distillation (Task 2.2) ---")
    
    residents = {"brain": MockResident("Brain")}
    hub = CognitiveHub(residents, None, None, lambda: True, None)
    
    raw_context = "User note from 2023 regarding PECI stress testing. High-fidelity results show 15% improvement."
    brief = await hub._distill_sovereign_brief(raw_context)
    
    print(f"  Result: {brief}")
    assert "[SOVEREIGN_BRIEF]" in brief
    print("[PASS] Context Distillation verified.")

async def test_memory_os_eviction():
    """Verifies Task 2.3: Memory-OS Eviction."""
    from nodes.archive_node import scribble_to_clipboard, read_clipboard
    # Note: archive_node.py uses globals for clipboard
    print("\n--- [TEST] Memory-OS Eviction (Task 2.3) ---")
    
    # Large content to force eviction (Limit is 8000)
    large_content = "A" * 5000
    await scribble_to_clipboard(large_content)
    await scribble_to_clipboard(large_content)
    
    clipboard = await read_clipboard()
    print(f"  Clipboard Length: {len(clipboard)}")
    # Should have evicted the first 5000, leaving only the second 5000 (plus formatting)
    assert len(clipboard) < 6000 
    print("[PASS] Clipboard Eviction verified.")

async def test_vibe_resonance_interjection():
    """Verifies Task 3.2: Neural Correction."""
    # This requires full Hub orchestration, we check for log warnings
    from logic.cognitive_hub import CognitiveHub
    print("\n--- [TEST] Neural Correction (Task 3.2) ---")
    
    class BadAuditor:
        async def audit_technical_truth(self, q, r, c): return True
        async def audit_vibe_alignment(self, r, v): return 0.2 # Low resonance
        
    residents = {"pinky": MockResident("Pinky"), "brain": MockResident("Brain")}
    hub = CognitiveHub(residents, None, None, lambda: True, None)
    hub.auditor = BadAuditor()
    hub.current_topic = "Casual"
    
    # Mock execute_dispatch to capture calls
    dispatches = []
    async def mock_dispatch(text, source, **kwargs):
        dispatches.append(source)
        
    hub.execute_dispatch = mock_dispatch
    
    # Simulate turn ending
    # We directly trigger the logic block from process_query
    # (Simplified)
    await hub.evaluate_grounding("Deep Thought", "I am a helpful assistant.", 0.8, None)
    
    print(f"  Dispatches: {dispatches}")
    # Should see 'Pinky (Reality Check)' or similar
    assert any("Pinky" in d for d in dispatches)
    print("[PASS] Interjection logic paths verified.")

if __name__ == "__main__":
    async def run_all():
        await test_sovereign_brief_distillation()
        await test_memory_os_eviction()
        await test_vibe_resonance_interjection()
    asyncio.run(run_all())
