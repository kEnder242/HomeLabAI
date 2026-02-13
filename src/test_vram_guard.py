import asyncio
import json
import pytest
import aiohttp
import os
import websockets

ATTENDANT_URL = "http://localhost:9999"
LAB_WS_URL = "ws://localhost:8765"

@pytest.mark.asyncio
async def test_vram_guard_stub_fallback():
    """
    Simulates a VRAM-constrained start and verifies the 'Stub' fallback.
    """
    # 1. Stop current lab
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ATTENDANT_URL}/stop")
        await session.post(f"{ATTENDANT_URL}/cleanup")
        
        # 2. Start lab with forced STUB engine
        payload = {
            "mode": "DEBUG_PINKY", 
            "engine": "STUB",
            "disable_ear": True
        }
        async with session.post(f"{ATTENDANT_URL}/start", json=payload) as resp:
            assert resp.status == 200
            data = await resp.json()
            print(f"Start Response: {data}")

    # 3. Wait for Lab READY
    print("Waiting for Lab READY...")
    await asyncio.sleep(5)
    async with aiohttp.ClientSession() as session:
        for i in range(30):
            try:
                async with session.get(f"{ATTENDANT_URL}/status") as resp:
                    data = await resp.json()
                    if data.get("full_lab_ready"):
                        print("Lab is READY.")
                        break
            except: pass
            await asyncio.sleep(2)
        else:
            pytest.fail("Lab failed to reach READY state.")

    # 4. Connect and send 'ask_brain' query
    async with websockets.connect(LAB_WS_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "3.5.0"}))
        await ws.send(json.dumps({"type": "text_input", "content": "FORCE_STUB_TEST: Ask the brain about quantum physics."}))
        
        # 5. Verify Stub Response
        found_stub = False
        captured = []
        try:
            async with asyncio.timeout(30):
                while not found_stub:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "brain" in data:
                        text = data["brain"]
                        source = data.get("brain_source", "Unknown")
                        captured.append(f"[{source}] {text}")
                        print(f"Received: {captured[-1]}")
                        if "VRAM is too tight" in text:
                            found_stub = True
        except asyncio.TimeoutError:
            print(f"Captured messages: {captured}")
            pytest.fail("Stub fallback failed to trigger.")

    assert found_stub, "Stub fallback message not found."
    print("[PASS] VRAM Guard Stub fallback verified.")

if __name__ == "__main__":
    asyncio.run(test_vram_guard_stub_fallback())
