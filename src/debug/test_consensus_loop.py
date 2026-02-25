import asyncio
import json
import websockets


async def test_consensus_loop():
    print("--- [TEST] Consensus Loop (Internal Debate) ---")

    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await asyncio.sleep(2)

            # Trigger a debate scenario
            topic = "Should the Lab prioritize Liger-Kernel integration for 8B models on Turing silicon despite the 11GB VRAM budget?"
            query = f"Trigger a peer-review debate on: {topic}"
            print(f"Topic: {topic}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))

            # Wait for debate progress and synthesis
            found_pinky = False
            found_brain = False
            found_synthesis = False

            for _ in range(30):
                resp = await websocket.recv()
                data = json.loads(resp)

                if "brain" in data:
                    src = data.get("brain_source", "Unknown")
                    txt = data["brain"]

                    if "Brain" in src:
                        found_brain = True
                        print(f"[REASONING]: {txt[:100]}...")
                    if "Pinky" in src:
                        found_pinky = True
                        print(f"[GROUNDING]: {txt[:100]}...")
                    if "Debate Synthesis" in txt:
                        found_synthesis = True
                        print("✅ DEBATE SYNTHESIS RECEIVED.")
                        break

                await asyncio.sleep(1)

            # Verification
            if found_pinky and found_brain:
                print("✅ Consensus Loop Verified: Both nodes participated.")
            else:
                print(
                    f"❌ FAILED: Node participation incomplete (Brain={found_brain}, Pinky={found_pinky})"
                )

            if found_synthesis:
                print("✅ PASSED: High-fidelity synthesis achieved.")
            else:
                print("❌ FAILED: Synthesis not found in final response.")

    except Exception as e:
        print(f"❌ Test Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_consensus_loop())
