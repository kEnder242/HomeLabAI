import asyncio
import json
import pytest
import websockets
import os

LAB_WS_URL = "ws://localhost:8765"
LOCK_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table.lock")

@pytest.mark.asyncio
async def test_lock_lifecycle():
    """
    Verifies that the round_table.lock is created on connection
    and removed on disconnection.
    """
    print("Connecting to Lab...")
    async with websockets.connect(LAB_WS_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "3.5.6"}))
        await asyncio.sleep(2) # Give hub time to write lock
        
        assert os.path.exists(LOCK_PATH), "Lock file should exist while connected."
        print("[PASS] Lock created on connection.")

    # 2. Verify removal
    await asyncio.sleep(2) # Give hub time to clean up
    assert not os.path.exists(LOCK_PATH), "Lock file should be removed after disconnection."
    print("[PASS] Lock removed on disconnection.")

if __name__ == "__main__":
    asyncio.run(test_lock_lifecycle())
