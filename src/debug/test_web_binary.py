import asyncio
import websockets
import json
import numpy as np
import time

async def test_web_binary_stream():
    uri = "ws://localhost:8765"
    print(f"🚀 Testing Web Binary Uplink to {uri}")
    
    try:
        async with websockets.connect(uri) as ws:
            # 1. Handshake
            await ws.send(json.dumps({"type": "handshake", "version": "2.4.1", "client": "web-test"}))
            resp = await ws.recv()
            print(f"✅ Handshake: {resp}")

            # 2. Stream Binary Chunks (Simulating browser output)
            # 16kHz, 1 second of audio
            chunk_size = 4096
            total_samples = 16000 * 3 # 3 seconds
            
            print(f"🎤 Sending {total_samples} samples in chunks of {chunk_size}...")
            
            for i in range(0, total_samples, chunk_size):
                # Dummy Sine Wave (440Hz)
                t = np.arange(i, i + chunk_size) / 16000
                samples = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
                
                # Send raw bytes (matches browser .buffer)
                await ws.send(samples.tobytes())
                await asyncio.sleep(chunk_size / 16000) # Real-time simulation
            
            print("✅ Binary stream finished.")
            
            # 3. Verify server produces a response
            # We don't expect actual speech recognition from a sine wave, 
            # but we want to see if the server crashes or logs errors.
            print("⏳ Waiting for server heartbeat/logs...")
            await asyncio.sleep(2)
            
    except Exception as e:
        print(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_web_binary_stream())
