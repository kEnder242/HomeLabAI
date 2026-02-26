import pytest
import aiohttp
import asyncio
import re
from test_utils import ensure_smart_lab, ATTENDANT_URL

@pytest.mark.asyncio
async def test_lab_attendant_full_cycle():
    """Tests the full lifecycle of the lab server via the attendant API."""
    # [FEAT-125] Use Smart-Reuse utility
    print("\n🏁 [STEP 1] Ensuring Lab is up and synchronized...")
    success = await ensure_smart_lab(disable_ear=False)
    assert success, "Failed to ensure Lab availability."

    async with aiohttp.ClientSession() as session:
        # [SMART] We are now guaranteed to have a synchronized Lab instance
        
        # 4. Wait for EarNode specifically
        print("⏳ Waiting for EarNode to initialize (background thread)...")
        ear_ready = False
        fingerprint_verified = False
        for _ in range(30): # Extra 30s for EarNode
            async with session.get(f"{ATTENDANT_URL}/logs") as resp:
                logs = await resp.text()
                
                # [FEAT-121] Verify Fingerprint Format [HASH:COMMIT:ROLE]
                if re.search(r"\[[0-9A-F]{4}:[0-9a-f]{7}:HUB\]", logs):
                    if not fingerprint_verified:
                        print("✅ Lab Fingerprint verified in logs.")
                        fingerprint_verified = True
                
                if "[STT] EarNode Ready." in logs:
                    ear_ready = True
                    print("✅ EarNode Online verified in logs.")
                    break
            await asyncio.sleep(2)

        assert fingerprint_verified, "Lab Fingerprint [FEAT-121] was not found in logs."
        assert ear_ready, "EarNode failed to initialize within timeout."

        # 5. Stop and Cleanup
        print("🛑 Stopping Lab Server...")
        await session.post(f"{ATTENDANT_URL}/stop")
        await session.post(f"{ATTENDANT_URL}/cleanup")

        async with session.get(f"{ATTENDANT_URL}/status") as resp:
            status = await resp.json()
            assert not status["lab_server_running"]
            print("✅ Cleanup verified.")

if __name__ == "__main__":
    asyncio.run(test_lab_attendant_full_cycle())
