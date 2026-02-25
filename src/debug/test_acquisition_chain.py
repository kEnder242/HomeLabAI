import asyncio
import json
import os
import websockets


async def test_acquisition_chain():
    print("--- [TEST] Multi-Stage Acquisition Chain ---")

    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await asyncio.sleep(1)

            # Trigger a year-based query
            query = "Analyze technical validation work from 2010."
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))

            # Wait for Brain's reasoned response
            for _ in range(15):
                resp = await websocket.recv()
                data = json.loads(resp)

                # Check server logs for [ACQUISITION] log if possible,
                # but here we check for the [HISTORICAL CONTEXT] shunt in the trace
                if data.get("brain_source") == "Brain":
                    break
                await asyncio.sleep(1)

            # Verification: Read the Neural Trace to prove the chain fired
            trace_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/logs/trace_brain.json")
            if os.path.exists(trace_path):
                with open(trace_path, "r") as f:
                    # Check the last 'send' entry
                    content = f.read()
                    if "[ACQUISITION Source: 2010.json]" in content:
                        print(
                            "✅ PASSED: Discovery -> Acquisition chain verified in Trace."
                        )
                        return True
                    else:
                        print("❌ FAILED: Acquisition label not found in prompt trace.")
                        return False
            else:
                print("❌ FAILED: Trace file not found.")
                return False

    except Exception as e:
        print(f"[ERROR] Test Error: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_acquisition_chain())
