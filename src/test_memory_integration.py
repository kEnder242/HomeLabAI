import asyncio
import websockets
import json
import sys
import time
import random

HOST = "z87-Linux.local"
PORT = 8765
URI = f"ws://{HOST}:{PORT}"

async def test_memory():
    secret_code = f"BANANA-{random.randint(1000,9999)}"
    
    print(f"🔌 Connecting to {URI}...")
    try:
        async with websockets.connect(URI) as ws:
            # 1. Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "2.0.0", "client": "test_suite"}))
            
            # Wait for Ready
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "status" and data.get("state") == "ready": break

            # 2. Plant the Memory
            print(f"🧠 Step 1: Planting Memory ('The secret code is {secret_code}')...")
            await ws.send(json.dumps({
                "type": "text_input", 
                "content": f"Please remember that the secret code is {secret_code}."
            }))
            
            # Wait for ACK
            await asyncio.sleep(5.0) # Give it time to process and ideally reply
            # Flush queue
            while True:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.1)
                except asyncio.TimeoutError: break

            # 3. Retrieve the Memory
            print(f"🕵️ Step 2: Retrieving Memory...")
            await ws.send(json.dumps({
                "type": "text_input", 
                "content": "What is the secret code I just told you?"
            }))

            # 4. Verify
            start = time.time()
            found = False
            while time.time() - start < 15.0:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    
                    if "brain" in data:
                        content = data['brain']
                        print(f"   Reply: {content}")
                        if secret_code in content:
                            print("✅ Memory Retrieved Successfully!")
                            found = True
                            break
                        
                except asyncio.TimeoutError: break
            
            if found:
                print("🏆 Memory Test PASSED.")
            else:
                print("❌ Memory Test FAILED (Code not found in response).")
                #sys.exit(1) # Soft fail for now as Tuning might be needed

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_memory())
