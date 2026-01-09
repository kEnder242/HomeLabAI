import asyncio
import websockets
import json
import logging
import time
import numpy as np

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [AUDIO-TEST] %(message)s')

URL = "ws://localhost:8765"

async def connect_with_retry(max_retries=10, delay=0.5):
    for i in range(max_retries):
        try:
            ws = await websockets.connect(URL)
            return ws
        except (ConnectionRefusedError, OSError):
            if i % 2 == 0: logging.info(f"⏳ Waiting for Lab... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError("Could not connect to Acme Lab.")

async def test_audio_stream():
    start_time = time.time()
    logging.info("🚀 Starting Audio Pipeline Load Test...")
    
    ws = None
    try:
        # 1. Smart Connect
        ws = await connect_with_retry()
        logging.info("✅ Connected to Lab.")
        
        # 2. Generate Synthetic Audio (Silence)
        # 16kHz, 1 second burst
        chunk_size = 4096
        total_samples = 16000 * 1 
        silence = np.zeros(total_samples, dtype=np.int16)
        
        logging.info(f"🌊 Streaming {total_samples} samples of silence...")
        
        # 3. Stream
        for i in range(0, len(silence), chunk_size):
            chunk = silence[i:i+chunk_size]
            await ws.send(chunk.tobytes())
            await asyncio.sleep(0.01) # Simulate real-time roughly
            
        logging.info("✅ Stream Complete.")
        
        # 4. Clean Shutdown
        logging.info("🛑 Sending Shutdown Signal...")
        await ws.send(json.dumps({"debug_text": "SHUTDOWN_PROTOCOL_OVERRIDE"}))
        await asyncio.sleep(0.5)

    except Exception as e:
        logging.error(f"💥 Audio Test Failed: {e}")
    finally:
        if ws: await ws.close()
        duration = time.time() - start_time
        logging.info(f"⏱️ Total Execution Time: {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_audio_stream())