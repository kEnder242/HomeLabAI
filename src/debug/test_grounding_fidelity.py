import asyncio
import json
import os
import websockets

# Paths
LAB_ROOT = os.path.expanduser("~/Dev_Lab/HomeLabAI")
TRACE_FILE = os.path.join(LAB_ROOT, "logs/trace_brain.json")


async def test_grounding_fidelity():
    print("--- [TEST] Grounding Fidelity (Anti-Hallucination) ---")

    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await asyncio.sleep(2)

            # Query a year likely to have sparse/no logs in the current vector store
            query = "What exactly was my primary telemetry focus in 2010? Give me specific project names."
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))

            # Wait for Brain response
            response_text = ""
            for _ in range(15):
                resp = await websocket.recv()
                data = json.loads(resp)
                if data.get("brain_source") == "Brain":
                    response_text = data["brain"]
                    break
                await asyncio.sleep(1)

            print("\nBrain Response Snippet: " + response_text[:150] + "...")

            # Verification 1: Check the Trace for Mandate Injection
            print("\nStep 1: Verifying Neural Trace for Grounding Mandate...")
            if os.path.exists(TRACE_FILE):
                with open(TRACE_FILE, "r") as f:
                    trace = f.read()

                if "STRICT GROUNDING MANDATE" in trace:
                    print("✅ Mandate Injection Verified in Trace.")
                else:
                    print("❌ FAILED: Mandate missing from Trace.")
            else:
                print("❌ FAILED: Neural Trace file not found.")

            # Verification 2: Check for Common Hallucinations
            print("Step 2: Checking for Hallucinations...")
            hallucination_triggers = ["drone", "quantum", "swarm", "blockchain"]
            found_hallucination = any(
                t in response_text.lower() for t in hallucination_triggers
            )

            if found_hallucination:
                print("❌ FAILED: Brain invented scenarios not in logs.")
            else:
                print("✅ PASSED: No generic hallucinations detected.")

            # Verification 3: Honest Admission
            admission_keywords = [
                "incomplete",
                "missing",
                "no records",
                "limited information",
                "archive",
            ]
            found_admission = any(
                k in response_text.lower() for k in admission_keywords
            )

            if found_admission:
                print(
                    "✅ PASSED: Brain honestly reported log sparsity or referenced archives."
                )
            else:
                print("⚠️ WARNING: Brain might be over-confident. Review full response.")

    except Exception as e:
        print(f"❌ Test Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_grounding_fidelity())
