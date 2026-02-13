import asyncio
import websockets
import json
import logging
import time

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [TEST] %(message)s')

URL = "ws://localhost:8765"

async def connect_with_retry(max_retries=10, delay=1.0):
    for i in range(max_retries):
        try:
            ws = await websockets.connect(URL)
            return ws
        except (ConnectionRefusedError, OSError):
            if i % 2 == 0: logging.info(f"⏳ Waiting for Lab... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError("Could not connect to Acme Lab after retries.")

async def test_tics():
    logging.info("🚀 Starting Nervous Tic Validation...")

    ws = None
    try:
        ws = await connect_with_retry()

        # 1. Wait for Ready
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "status" and msg.get("state") == "ready":
                break

        # 2. Send Delegate Command
        logging.info("📤 Sending slow query...")
        await ws.send(json.dumps({"debug_text": "Ask the Brain to calculate the meaning of life."}))

        # 3. Listen for Tics
        tic_received = False
        brain_received = False

        start_wait = time.time()
        async for msg_raw in ws:
            # Safety timeout
            if time.time() - start_wait > 10.0:
                raise TimeoutError("Test timed out waiting for Brain.")

            msg = json.loads(msg_raw)

            # Check for Tic
            if "brain_source" in msg and "Reflex" in msg["brain_source"]:
                logging.info(f"✅ Nervous Tic Received: '{msg['brain']}'")
                tic_received = True

            # Check for Final Brain Output (via debug event or direct reply??)
            # In MOCK mode, the loop continues. We look for the Debug Event broadcast.
            if msg.get("type") == "debug" and msg.get("event") == "BRAIN_OUTPUT":
                logging.info("✅ Brain Output Received.")
                brain_received = True
                break

        if not tic_received:
            raise AssertionError("Brain finished but NO Nervous Tic was received!")

        logging.info("✅ Tic Logic Validated.")

        # 4. Clean Shutdown
        await ws.send(json.dumps({"debug_text": "SHUTDOWN_PROTOCOL_OVERRIDE"}))

    except Exception as e:
        logging.error(f"💥 Validation Failed: {e}")
        exit(1)
    finally:
        if ws:
            await ws.close()

if __name__ == "__main__":
    asyncio.run(test_tics())