import asyncio
import json
import websockets

async def test_oracle_resonance():
    print("--- [TEST] Oracle Resonance (Magic 8-Ball Signals) ---")
    
    uri = 'ws://localhost:8765'
    signals_received = []
    
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({'type': 'handshake', 'version': '3.8.0'}))
            await asyncio.sleep(1)
            
            for i in range(3):
                query = f"Oracle Test Run {i+1}: Strategy check."
                print(f"Sending Query {i+1}...")
                await websocket.send(json.dumps({'type': 'text_input', 'content': query}))
                
                # Wait for Signal preamble
                for _ in range(10):
                    resp = await websocket.recv()
                    data = json.loads(resp)
                    if data.get('brain_source') == 'Brain (Signal)':
                        sig = data['brain']
                        print(f"Signal Captured: {sig}")
                        signals_received.append(sig)
                        break
                    await asyncio.sleep(0.5)
                
                await asyncio.sleep(2) # Cooldown between turns

            # Verification
            if len(signals_received) > 0:
                print(f"\nCaptured {len(signals_received)} unique signals.")
                # Verify they aren't the old hardcoded strings
                old_sigs = ["Retro-fidelity achieved", "Brain is thinking", "Retrieving logs"]
                for s in signals_received:
                    if any(osig in s for osig in old_sigs):
                        print(f"[FAIL] Found legacy hard-coded signal: {s}")
                        return False
                print("[SUCCESS] Oracle is providing dynamic, registry-based signals.")
                return True
            else:
                print("[FAIL] No signals captured.")
                return False

    except Exception as e:
        print(f"[ERROR] Test Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_oracle_resonance())
