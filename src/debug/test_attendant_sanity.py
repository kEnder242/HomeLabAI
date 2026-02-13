import asyncio
import aiohttp
import json
import os
import pytest

ATTENDANT_URL = "http://localhost:9999"
STATUS_JSON_PATH = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/status.json"

@pytest.mark.asyncio
async def test_attendant_heartbeat():
    """Verifies Attendant is alive and responding."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ATTENDANT_URL}/status") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "attendant_pid" in data
            print(f"[PASS] Attendant Heartbeat: PID {data['attendant_pid']}")

@pytest.mark.asyncio
async def test_status_json_update():
    """Verifies Attendant can write to status.json."""
    # 1. Capture current mtime
    initial_mtime = os.path.getmtime(STATUS_JSON_PATH) if os.path.exists(STATUS_JSON_PATH) else 0
    
    # 2. Trigger status check
    async with aiohttp.ClientSession() as session:
        await session.get(f"{ATTENDANT_URL}/status")
    
    # 3. Verify mtime increased
    await asyncio.sleep(1) # Wait for disk write
    new_mtime = os.path.getmtime(STATUS_JSON_PATH)
    assert new_mtime > initial_mtime
    
    # 4. Verify content is valid JSON
    with open(STATUS_JSON_PATH, "r") as f:
        data = json.load(f)
        assert "timestamp" in data
        assert "vitals" in data
    print(f"[PASS] status.json updated at {data['timestamp']}")

if __name__ == "__main__":
    asyncio.run(test_attendant_heartbeat())
    asyncio.run(test_status_json_update())
