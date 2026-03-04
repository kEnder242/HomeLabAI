import asyncio
import json
import pytest
import websockets

@pytest.mark.asyncio
async def test_pi_to_21_digits_bundled_flow():
    """
    [FEAT-153] Verifies Bundled Bicameral Flow:
    1. User asks for pi to 21 digits.
    2. Hub coordinates parallel turns.
    3. Verifies both Pinky's quip and Brain's technical answer are received.
    """
    url = "ws://127.0.0.1:8765"
    async with websockets.connect(url) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake"}))
        print("[BOOT] Handshake sent.")

        # 2. Fire Query
        query = "What is the value of pi to exactly 21 digits? I need the technical truth."
        await ws.send(json.dumps({"type": "text_input", "content": query}))

        # 3. Collector Loop
        start_t = time.time() if 'time' in globals() else 0 # Simple check
        import time
        start_t = time.time()
        
        bundle = []
        found_pi = False
        found_quip = False

        while time.time() - start_t < 60.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                
                source = data.get("brain_source") or data.get("source")
                text = data.get("brain") or data.get("text")
                
                if not text or not source:
                    continue

                print(f"  [{source}] {text[:50]}...")
                
                # Check for Pinky's Reflex/Foil
                if "Pinky" in source:
                    found_quip = True
                
                # Check for technical answer
                if "3.1415" in text:
                    found_pi = True
                
                if found_pi and found_quip:
                    print("✅ BUNDLE COMPLETE: Quip and Truth received.")
                    break
            except asyncio.TimeoutError:
                continue

        assert found_quip, "Pinky failed to provide narrative foil."
        assert found_pi, "Brain failed to provide technical digits."

if __name__ == "__main__":
    asyncio.run(test_pi_to_21_digits_bundled_flow())
