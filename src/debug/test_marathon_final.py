import asyncio
import json
import websockets

ATTENDANT_URL = "http://localhost:9999"
LAB_WS_URL = "ws://localhost:8765"

async def test_vllm_marathon_flows():
    print("Connecting to vLLM Lab...")
    async with websockets.connect(LAB_WS_URL) as ws:
        await ws.send(json.dumps({"type": "handshake", "version": "3.5.7"}))

        # 1. Test Save Reaction
        print("Testing Strategic Vibe Check (vLLM)...")
        await ws.send(json.dumps({
            "type": "workspace_save",
            "filename": "vllm_test.py",
            "content": "import time\\ndef race_condition():\\n    global counter\\n    counter += 1"
        }))

        found_pinky = False
        found_brain = False
        async with asyncio.timeout(60):
            while not (found_pinky and found_brain):
                msg = await ws.recv()
                data = json.loads(msg)
                if "brain" in data:
                    text = data["brain"]
                    source = data.get("brain_source", "")
                    if "noticed you saved" in text and source == "Pinky":
                        print(f"Captured Pinky: {text[:50]}...")
                        found_pinky = True
                    elif source == "The Brain":
                        print(f"Captured Brain Insight: {text[:100]}...")
                        found_brain = True

        # 2. Test Complex Reasoning
        print("\nTesting vLLM Reasoning Stability...")
        await ws.send(json.dumps({"type": "text_input", "content": "Explain PagedAttention in 2 sentences."}))

        found_ans = False
        async with asyncio.timeout(60):
            while not found_ans:
                msg = await ws.recv()
                data = json.loads(msg)
                if "brain" in data:
                    text = data["brain"]
                    if len(text) > 20:
                        print(f"Captured Answer: {text[:100]}...")
                        found_ans = True

    print("\n[PASS] vLLM Marathon flows verified nominal.")

if __name__ == "__main__":
    asyncio.run(test_vllm_marathon_flows())
