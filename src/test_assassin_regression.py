import socket
import aiohttp
import asyncio
import sys

ATTENDANT_URL = "http://localhost:9999"

async def test_assassin_regression():
    print("--- [TEST] FEAT-119: Socket-Aware Assassin ---")
    
    async with aiohttp.ClientSession() as session:
        # 0. Stop current Lab
        print("🛑 Stopping Lab...")
        await session.post(f"{ATTENDANT_URL}/stop")
        await asyncio.sleep(2)

        # 1. Manually hijack port 8765
        print("⚠️ Hijacking port 8765...")
        hijacker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Use REUSEADDR to hijack it even if in TIME_WAIT
        hijacker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            hijacker.bind(("0.0.0.0", 8765))
            hijacker.listen(1)
            print("✅ Port 8765 hijacked.")
        except Exception as e:
            print(f"❌ Failed to hijack port: {e}")
            return

        # 2. Trigger Lab Start via Attendant
        print("🚀 Triggering Lab Start (Assassin should kill me)...")
        try:
            async with session.post(f"{ATTENDANT_URL}/start", json={"mode": "SERVICE_UNATTENDED", "disable_ear": True}) as resp:
                data = await resp.json()
                print(f"  Response: {data.get('status')}")
        except Exception as e:
            print(f"  Attendant request failed (expected if it kills the test process? No, should kill group): {e}")

        # 3. Wait for Readiness
        print("⏳ Waiting for Lab to reclaim port and reach READY...")
        ready = False
        for _ in range(30):
            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    status = await resp.json()
                    if status.get("lab_server_running") and status.get("full_lab_ready"):
                        ready = True
                        print("✅ Lab reclaimed port 8765 successfully!")
                        break
            except Exception:
                pass
            await asyncio.sleep(2)

        # Cleanup
        hijacker.close()
        
        if not ready:
            print("❌ FAILED: Lab could not reclaim port 8765.")
            sys.exit(1)
        else:
            print("🏁 [PASS] Socket-Aware Assassin regression test successful.")

if __name__ == "__main__":
    asyncio.run(test_assassin_regression())
