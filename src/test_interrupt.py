import asyncio
import websockets
import json
import logging
import time

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [INTERRUPT-TEST] %(message)s')

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

async def test_interrupt():
    start_time = time.time()
    logging.info("🚀 Starting Round Table Interrupt Test...")
    
    ws = None
    try:
        # 1. Smart Connect
        ws = await connect_with_retry()
        logging.info("✅ Connected to Lab.")

        # 2. Wait for Ready State
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "status" and msg.get("state") == "ready":
                logging.info("✅ Lab is Ready.")
                break
        
        # 3. Send Complex Query
        test_query = "Ask the Brain to write a long poem about cheese."
        logging.info(f"📤 Sending Query: '{test_query}'")
        await ws.send(json.dumps({"debug_text": test_query}))

        # 4. Wait for Delegation Start
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "debug" and msg.get("event") == "PINKY_DECISION":
                if msg.get("data").get("tool") == "delegate_to_brain":
                    logging.info("✅ Brain Delegation Started.")
                    break

        # 5. Send BARGE_IN Signal
        logging.info("⚡ SENDING BARGE_IN SIGNAL!")
        await ws.send(json.dumps({"debug_text": "BARGE_IN"}))

        # 6. Verify Interruption Response
        interrupted = False
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                if msg.get("brain_source") == "Pinky" and "Stopping" in msg.get("brain"):
                    logging.info("✅ Interruption Response Received: 'Stopping... Narf!'")
                    interrupted = True
                    break
        except asyncio.TimeoutError:
            logging.error("❌ Test Timed Out waiting for interrupt response!")

        assert interrupted, "The session was not interrupted correctly."
        logging.info("✨ INTERRUPT TEST PASSED!")

        # 7. Clean Shutdown
        logging.info("🛑 Sending Shutdown Signal...")
        await ws.send(json.dumps({"debug_text": "SHUTDOWN_PROTOCOL_OVERRIDE"}))
        await asyncio.sleep(0.5)

    except Exception as e:
        logging.error(f"💥 Interrupt Test Failed: {e}")
    finally:
        if ws: await ws.close()
        duration = time.time() - start_time
        logging.info(f"⏱️ Total Execution Time: {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_interrupt())
