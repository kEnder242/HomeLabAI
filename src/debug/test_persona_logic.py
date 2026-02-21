import asyncio
import json
import websockets
import time
import logging

# Configuration
HUB_URL = "ws://localhost:8765"

async def test_persona_and_tics():
    """Verifies Pinky's personality commentary and nervous tics."""
    print("\n--- 🏁 STARTING PERSONA & TIC VALIDATION ---")
    
    async with websockets.connect(HUB_URL) as ws:
        # 1. Address the Brain directly
        print("[TEST] Addressing the Brain...")
        await ws.send(json.dumps({"type": "text_input", "content": "Brain, what is the status of our silicon?"}))
        
        # Expect Pinky interjection
        start_t = time.time()
        pinky_seen = False
        while time.time() - start_t < 15:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get('brain_source') == 'Pinky' and "Left Hemisphere" in data.get('brain', ''):
                print(f"[PASS] Pinky personality interjection: {data['brain']}")
                pinky_seen = True
                break
        
        if not pinky_seen:
            print("[FAIL] Pinky failed to interject when Brain was addressed.")
            return False

        # 2. Test slow query for "Nervous Tics"
        print("[TEST] Sending slow complex query for tics...")
        # A query that doesn't explicitly mention 'brain' but is long
        await ws.send(json.dumps({
            "type": "text_input", 
            "content": "Perform a comprehensive historical analysis of every validation error we encountered in the 2021 PCIe sweep."
        }))
        
        start_t = time.time()
        tics_seen = 0
        while time.time() - start_t < 60:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get('brain_source') == 'Pinky' and ("Poit!" in data.get('brain', '') or "heavy-lift" in data.get('brain', '')):
                print(f"[PASS] Pinky progress tic seen: {data['brain']}")
                tics_seen += 1
                if tics_seen >= 1: break
        
        if tics_seen == 0:
            print("[FAIL] No nervous tics seen during long query.")
            return False

    print("--- ✅ PERSONA & TIC VALIDATION SUCCESSFUL ---")
    return True

if __name__ == "__main__":
    if asyncio.run(test_persona_and_tics()):
        exit(0)
    else:
        exit(1)
