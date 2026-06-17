import asyncio
import aiohttp
import pytest

ATTENDANT_URL = "http://localhost:8765"

async def test_attendant_heartbeat():
    async with aiohttp.ClientSession() as session:
        url = f"{ATTENDANT_URL}/status"
        async with session.get(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["state"] in ["WAKING", "READY"]
            print(f"[PASS] Attendant Heartbeat: {data['state']}")

if __name__ == "__main__":
    asyncio.run(test_attendant_heartbeat())
