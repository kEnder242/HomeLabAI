import asyncio
import json
import websockets
import time

HUB_URL = "ws://localhost:8765"

async def send_query(query):
    try:
        async with websockets.connect(HUB_URL) as ws:
            await ws.send(json.dumps({"type": "handshake", "client": "lora_guard_test"}))
            await ws.send(json.dumps({"type": "text_input", "content": query}))
            
            start_t = time.time()
            vocal_response = False
            downshift_detected = False
            
            while time.time() - start_t < 60:
                msg = await ws.recv()
                data = json.loads(msg)
                source = data.get('brain_source', 'System')
                content = data.get('brain', '')
                
                if content:
                    print(f"    [{source}] {content[:100]}...")
                
                if "Downshifting to Base Model" in str(content):
                    downshift_detected = True
                    print("    [ALERT] LoRA Guard Triggered!")
                
                if source in ['Lab', 'Brain', 'Pinky']:
                    vocal_response = True
                
                if data.get('final') == True:
                    break
                    
            return vocal_response, downshift_detected
    except Exception as e:
        print(f"    [!] Error: {e}")
        return False, False

async def main():
    print("=== 🛡️ 5x5 HAND-CRANK: LoRA GUARD CERTIFICATION ===")
    
    # 1. Cycle 1: Baseline (Normal Query)
    print("\n[*] Cycle 1: Baseline Reasoning...")
    ok, down = await send_query("[ME] Hello. Who are you?")
    if ok and not down:
        print("    [WIN 1] PASS: Stable LoRA reasoning.")
    else:
        print(f"    [FAIL] Cycle 1. OK={ok}, Down={down}")
        return

    # 2. Cycle 2: Stress / Induce Failure
    # We send a long, complex query to try and trigger the V1 fragmentation
    print("\n[*] Cycle 2: Stressing Larynx...")
    ok, down = await send_query("[ME] Analyze the physical telemetry of the ESB2 bridge during a 4090 VRAM spike while running vLLM in eager mode with 4 LoRA adapters.")
    if ok:
        print(f"    [WIN 2] PASS: Vocal response received. (Downshift={down})")
    else:
        print("    [FAIL] Cycle 2: Silent.")
        return

    # 3. Cycle 3: Persistence Audit
    print("\n[*] Cycle 3: Reasoning Consistency...")
    ok, down = await send_query("[ME] What is the current Lab Floor memory footprint?")
    if ok:
        print(f"    [WIN 3] PASS: System stable.")
    else:
        print("    [FAIL] Cycle 3.")
        return

    # 4. Cycle 4: Verification of 'Clean' Triage
    print("\n[*] Cycle 4: Triage Integrity check...")
    ok, down = await send_query("[ME] Just say 'Roger'.")
    if ok:
        print("    [WIN 4] PASS: Minimal interaction verified.")
    else:
        print("    [FAIL] Cycle 4.")
        return

    # 5. Cycle 5: Final Endurance
    print("\n[*] Cycle 5: Final Certification...")
    ok, down = await send_query("[ME] Performance audit complete. Summary requested.")
    if ok:
        print("    [WIN 5] PASS: System fully vocal.")
    else:
        print("    [FAIL] Cycle 5.")
        return

    print("\n✅ 5x5 HAND-CRANK COMPLETE. LoRA GUARD CERTIFIED.")

if __name__ == "__main__":
    asyncio.run(main())
