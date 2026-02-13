import asyncio
import json
import pytest
import aiohttp
import os

ATTENDANT_URL = "http://localhost:9999"

@pytest.mark.asyncio
async def test_vram_invalidation():
    """
    Verifies that the Attendant can force-release VRAM via SIGTERM.
    1. Start a dummy 'lab' process.
    2. Trigger start with an engine that requires more headroom.
    3. Verify old process is dead.
    """
    async with aiohttp.ClientSession() as session:
        # 1. Ensure lab is running
        await session.post(f"{ATTENDANT_URL}/start", json={"mode": "SERVICE_UNATTENDED", "engine": "OLLAMA"})
        await asyncio.sleep(2) # Minimal start time
        
        status_resp = await session.get(f"{ATTENDANT_URL}/status")
        status = await status_resp.json()
        old_pid = status.get("lab_pid")
        assert old_pid is not None, "Lab should be running."
        
        # 2. Trigger invalidation via a new 'start' request with preferred engine
        # We'll fake a need for vLLM which should trigger invalidation of OLLAMA
        print(f"Triggering invalidation of PID {old_pid}...")
        payload = {"mode": "SERVICE_UNATTENDED", "engine": "vLLM"}
        async with session.post(f"{ATTENDANT_URL}/start", json=payload) as resp:
            data = await resp.json()
            assert resp.status == 200
            new_pid = data.get("pid")
            
        assert new_pid != old_pid, "Attendant should have started a NEW process."
        
        # Verify old process is gone
        try:
            os.kill(old_pid, 0)
            pytest.fail(f"Old PID {old_pid} is still alive!")
        except ProcessLookupError:
            print("[PASS] Old process invalidated correctly.")

if __name__ == "__main__":
    asyncio.run(test_vram_invalidation())
