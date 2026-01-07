import asyncio
import websockets
import json
import numpy as np

PORT = 8765
HOST = "z87-Linux.local"

async def test_run():
    uri = f"ws://{HOST}:{PORT}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected. Sending 3 seconds of silence...")
            
            # 16kHz audio, 2 seconds, zeros
            chunk_size = 2048
            total_samples = 16000 * 3
            silence = np.zeros(total_samples, dtype=np.int16)
            
            for i in range(0, len(silence), chunk_size):
                chunk = silence[i:i+chunk_size]
                await websocket.send(chunk.tobytes())
                await asyncio.sleep(0.05)
                
            print("Done sending. Disconnecting.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
