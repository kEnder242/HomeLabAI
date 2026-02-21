import asyncio
import json
import pytest
import websockets

VERSION = "3.5.9"

@pytest.mark.asyncio
async def test_pi_to_20_digits_flow():
    """
    Verifies the complete Bicameral flow for a complex query:
    1. User asks 'pi to 21 digits'.
    2. Pinky delegates via 'ask_brain'.
    3. Brain provides the insight.
    4. Pinky + Brain engage in banter/synthesis.
    """
    url = "ws://127.0.0.1:8765"
    async with websockets.connect(url) as ws:
    
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake", "version": VERSION}))
        
        # Consume handshake/initial messages until we get a cabinet or status
        async with asyncio.timeout(5):
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("type") in ["cabinet", "status"]:
                    print(f"[HANDSHAKE] Received: {data.get('type')}")
                    # Handshake can have multiple initial messages
                    if data.get("type") == "cabinet":
                        break

        # 2. Send Query
        query = "What is the value of pi to exactly 21 digits?"
        await ws.send(json.dumps({"type": "text_input", "content": query}))

        # 3. Monitor for Flow Events
        events = []
        try:
            # High timeout for Brain reasoning
            async with asyncio.timeout(60):
                while len(events) < 2: # At least Delegation and Answer
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    text = data.get("brain", "")
                    source = data.get("brain_source", "Unknown")
                    if text:
                        print(f"[{source}]: {text[:50]}...")

                    # Handle Live Flow
                    msg_low = text.lower()
                    if ("analytical nodes" in msg_low or "shadow hemisphere" in msg_low or "strategic detected" in msg_low or "engaging" in msg_low) and source == "System":
                        if "DELEGATION" not in events:
                            print(f"✅ DELEGATION Detected: {text[:30]}...")
                            events.append("DELEGATION")
                    
                    if ("3.14" in text):
                        if "BRAIN_ANSWER" not in events:
                            print(f"✅ BRAIN_ANSWER Detected from {source}: {text[:30]}...")
                            events.append("BRAIN_ANSWER")
                    
                    if source == "Pinky" and "DELEGATION" in events:
                        if "FINAL_WORD" not in events:
                            print(f"✅ FINAL_WORD Detected: {text[:30]}...")
                            events.append("FINAL_WORD")
                    
                    if "DELEGATION" in events and "BRAIN_ANSWER" in events and "FINAL_WORD" in events:
                        break

        except asyncio.TimeoutError:
            pytest.fail(f"Flow timed out. Events captured: {events}")

        # Assert full flow
        assert "DELEGATION" in events, "Pinky failed to delegate."
        assert "BRAIN_ANSWER" in events, "Brain failed to provide the digits."
        assert "FINAL_WORD" in events, "Mind failed to conclude the interaction."

if __name__ == "__main__":
    asyncio.run(test_pi_to_20_digits_flow())
