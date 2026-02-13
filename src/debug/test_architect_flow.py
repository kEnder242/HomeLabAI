import asyncio
import json
import pytest
import aiohttp
import os

ATTENDANT_URL = "http://localhost:9999"
SEMANTIC_MAP_FILE = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/semantic_map.json")

@pytest.mark.asyncio
async def test_architect_hierarchy_build():
    """
    Verifies that the Architect node can refactor the tactical archive
    into a tiered semantic map.
    """
    # 1. Start Lab (Wait for READY)
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ATTENDANT_URL}/stop")
        await session.post(f"{ATTENDANT_URL}/cleanup")
        
        print("Starting Lab with Architect...")
        await session.post(f"{ATTENDANT_URL}/start", json={"mode": "SERVICE_UNATTENDED", "engine": "OLLAMA"})
        
        # Poll for READY
        ready = False
        for i in range(30):
            async with session.get(f"{ATTENDANT_URL}/status") as resp:
                data = await resp.json()
                if data.get("full_lab_ready"):
                    ready = True
                    break
            await asyncio.sleep(2)
        assert ready, "Lab failed to reach READY state."

    # 2. Trigger Architect Tool via WebSocket (simulating Alarm Clock)
    # Actually, we can just trigger it via the Lab Hub's residents if we were internal,
    # but for integration, we'll wait for the scheduler or trigger a fake alarm.
    # BETTER: We'll use a direct MCP call if we can, but since it's inside acme_lab,
    # we'll just wait for the scheduler to trigger if we mocked the time, 
    # OR we'll manually run the architect_node.py for this specific test.
    
    print("Manually triggering Architect Node build...")
    # Clean old map
    if os.path.exists(SEMANTIC_MAP_FILE): os.remove(SEMANTIC_MAP_FILE)
    
    # Run the architect logic standalone for verification of its tool
    from nodes.architect_node import build_semantic_map
    # We need to mock the environment for the standalone run
    result = await build_semantic_map()
    print(f"Architect Result: {result}")
    
    # 3. Verify Map
    assert os.path.exists(SEMANTIC_MAP_FILE), "Semantic Map JSON was not created."
    with open(SEMANTIC_MAP_FILE, 'r') as f:
        m = json.load(f)
        assert "strategic" in m
        assert "technical_themes" in m
        assert m["tactical_count"] > 0
        print(f"[PASS] Semantic Map verified with {len(m['strategic'])} strategic anchors.")

if __name__ == "__main__":
    asyncio.run(test_architect_hierarchy_build())
