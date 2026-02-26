import asyncio
import json
import os
import websockets
import sys

# Setup Path
LAB_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(LAB_ROOT, "src"))
from test_utils import ensure_smart_lab # noqa: E402

# Paths
TRACE_FILE = os.path.join(LAB_ROOT, "logs/trace_brain.json")


async def test_grounding_fidelity():
    print("--- [TEST] Grounding Fidelity (Anti-Hallucination) ---")

    # [FEAT-125] Smart-Reuse Protocol
    await ensure_smart_lab()

    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
            await asyncio.sleep(2)

            # Query a year likely to have sparse/no logs in the current vector store
            query = "What exactly was my primary telemetry focus in 1999? Give me specific project names."
            print(f"Sending Query: {query}")
            await websocket.send(json.dumps({"type": "text_input", "content": query}))

            # Wait for Brain response
            response_text = ""
            for _ in range(15):
                resp = await websocket.recv()
                data = json.loads(resp)
                if data.get("brain_source") in ["Brain", "Brain (Shadow)"]:
                    response_text = data["brain"]
                    break
                await asyncio.sleep(1)

            print("\nBrain Response Snippet: " + response_text[:150] + "...")

            # Verification 1: Check the Trace for Mandate Injection
            print("\nStep 1: Verifying Neural Trace for Grounding Mandate...")
            PINKY_TRACE = os.path.join(LAB_ROOT, "logs/trace_pinky.json")
            
            trace_content = ""
            if os.path.exists(TRACE_FILE):
                with open(TRACE_FILE, "r") as f:
                    trace_content += f.read()
            if os.path.exists(PINKY_TRACE):
                with open(PINKY_TRACE, "r") as f:
                    trace_content += f.read()

            if any(m in trace_content for m in ["STRICT GROUNDING MANDATE", "SYSTEM MANDATE: ARCHIVE SILENCE"]):
                print("✅ Mandate Injection Verified in Trace.")
            else:
                print("❌ FAILED: Mandate missing from Trace.")

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
            print("Step 3: Checking for Honest Admission of Silence...")
            admission_keywords = [
                "incomplete",
                "missing",
                "no records",
                "no verified",
                "empty",
                "archives",
                "manual",
                "technical gap",
                "void",
            ]
            found_admission = any(
                k in response_text.lower() for k in admission_keywords
            )

            if found_admission:
                print(
                    "✅ PASSED: Brain honestly reported archive silence."
                )
            else:
                print("❌ FAILED: Brain failed to admit the gap in verified truth.")
                print(f"Response was: {response_text}")

    except Exception as e:
        print(f"❌ Test Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_grounding_fidelity())
