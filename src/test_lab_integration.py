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
                    print(f"✅ Lab is READY!")
                    break
            await asyncio.sleep(2)

        assert ready, "Lab failed to reach READY state within timeout."

        # 4. Wait for EarNode specifically
        print("⏳ Waiting for EarNode to initialize (background thread)...")
        ear_ready = False
        for _ in range(30): # Extra 30s for EarNode
            async with session.get(f"{ATTENDANT_URL}/logs") as resp:
                logs = await resp.text()
                if "[STT] EarNode Ready." in logs:
                    ear_ready = True
                    print("✅ EarNode Online verified in logs.")
                    break
            await asyncio.sleep(2)

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
