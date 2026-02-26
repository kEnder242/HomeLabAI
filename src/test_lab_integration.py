import pytest
import aiohttp
import asyncio

# --- Configuration ---
ATTENDANT_URL = "http://localhost:9999"

@pytest.mark.asyncio
async def test_lab_attendant_full_cycle():
    """Tests the full lifecycle of the lab server via the attendant API."""
    async with aiohttp.ClientSession() as session:
        # 1. Ensure it's stopped/cleaned
        await session.post(f"{ATTENDANT_URL}/stop")
        await session.post(f"{ATTENDANT_URL}/cleanup")

        # 2. Start with EarNode enabled
        print("\n🚀 Starting Lab Server with EarNode...")
        async with session.post(f"{ATTENDANT_URL}/start", json={"disable_ear": False}) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
            # Note: pid is no longer returned directly in start

        # 3. Poll for READY status
        print("⏳ Waiting for Lab to reach READY state...")
        ready = False
        for _ in range(60): # 60 seconds timeout
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                status = await resp.json()
                if status["full_lab_ready"]:
                    ready = True
                    print("✅ Lab is READY!")
                    break
            await asyncio.sleep(2)

        assert ready, "Lab failed to reach READY state within timeout."

        # 4. Wait for EarNode specifically
        print("⏳ Waiting for EarNode to initialize (background thread)...")
        ear_ready = False
        fingerprint_verified = False
        for _ in range(30): # Extra 30s for EarNode
            async with session.get(f"{ATTENDANT_URL}/logs") as resp:
                logs = await resp.text()
                
                # [FEAT-121] Verify Fingerprint Format [HASH:COMMIT:ROLE]
                import re
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
