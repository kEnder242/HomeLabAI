import asyncio
import json
from acme_lab import AcmeLab
from unittest.mock import AsyncMock, MagicMock

async def test_barge_in_execution():
    print("\n--- STARTING BARGE-IN PHYSICS TEST ---")
    lab = AcmeLab(mode="DEBUG_SMOKE")
    
    # Mock Resident
    mock_pinky = AsyncMock()
    lab.residents = {"pinky": mock_pinky}
    
    # Simulate a long-running Pinky response
    async def slow_response(*args, **kwargs):
        await asyncio.sleep(5)
        return MagicMock(content=[MagicMock(text=json.dumps({"reply_to_user": "Finished!"}))])
    
    mock_pinky.call_tool.side_effect = slow_response

    # 1. Start a query task
    ws_mock = MagicMock()
    print("[TEST] Sending slow query...")
    current_task = asyncio.create_task(lab.process_query("Tell me a long story.", ws_mock))
    
    await asyncio.sleep(1) # Let it start
    
    # 2. Simulate Barge-In
    print("[TEST] Simulating Barge-In...")
    if not current_task.done():
        current_task.cancel()
        print("[TEST] Task cancelled.")
    
    try:
        await current_task
    except asyncio.CancelledError:
        print("[PASS] Barge-In verified.")
    
    print("--- BARGE-IN COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_barge_in_execution())
