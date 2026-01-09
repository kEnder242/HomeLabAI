import asyncio
import websockets
import json
import logging
import time

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [TEST] %(message)s')

URL = "ws://localhost:8765"

async def connect_with_retry(max_retries=10, delay=0.5):
    for i in range(max_retries):
        try:
            ws = await websockets.connect(URL)
            return ws
        except (ConnectionRefusedError, OSError):
            if i % 2 == 0: logging.info(f"⏳ Waiting for Lab... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError("Could not connect to Acme Lab after retries.")

async def test_all_flows():
    start_time = time.time()
    logging.info("🚀 Starting Round Table Flow Validation (Fast-Track)...")
    
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
        
        # TEST 1: Baseline Greeting (Direct Reply)
        test_query_1 = "Hi Pinky!"
        logging.info(f"📤 Sending Baseline: '{test_query_1}'")
        await ws.send(json.dumps({"debug_text": test_query_1}))

        async for msg_raw in ws:
            msg = json.loads(msg_raw)
            if msg.get("type") == "debug" and msg.get("event") == "PINKY_DECISION":
                decision = msg.get("data")
                if decision.get("tool") == "reply_to_user":
                    logging.info("✅ Baseline Reply Validated.")
                    break

        # TEST 2: Delegation (The Loop)
        test_query_2 = "Ask the Brain to summarize the moon mission."
        logging.info(f"📤 Sending Delegation: '{test_query_2}'")
        await ws.send(json.dumps({"debug_text": test_query_2}))

        captured_tools = []
        async for msg_raw in ws:
            msg = json.loads(msg_raw)
            if msg.get("type") == "debug" and msg.get("event") == "PINKY_DECISION":
                tool = msg.get("data").get("tool")
                captured_tools.append(tool)
                if tool == "reply_to_user":
                    break
        
        assert "delegate_to_brain" in captured_tools
        logging.info("✅ Delegation Flow Validated.")

        # 3. Clean Shutdown
        logging.info("🛑 Sending Shutdown Signal...")
        await ws.send(json.dumps({"debug_text": "SHUTDOWN_PROTOCOL_OVERRIDE"}))
        await asyncio.sleep(0.5) # Give it a moment to process

    except Exception as e:
        logging.error(f"💥 Validation Failed: {e}")
    finally:
        if ws: await ws.close()
        duration = time.time() - start_time
        logging.info(f"⏱️ Total Execution Time: {duration:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_all_flows())
