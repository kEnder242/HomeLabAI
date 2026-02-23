import asyncio
import json
import pytest
import websockets

VERSION = "3.8.0"

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
        events = set()
        try:
            # High timeout for Brain reasoning
            async with asyncio.timeout(60):
                while len(events) < 3: # Coordination, Answer, and Completion
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    text = data.get("brain", "")
                    source = data.get("brain_source", "Unknown")
                    if text:
                        print(f"[{source}]: {text[:50]}...")

                    # Handle Live Flow
                    msg_low = text.lower()
                    
                    # 1. Detection of Coordination (Signal or System)
                    if source in ["System", "Brain (Signal)"] or ("check with" in text):
                        if "COORDINATION" not in events:
                            print(f"✅ COORDINATION Detected: {text[:30]}...")
                            events.add("COORDINATION")
                    
                    # 2. Detection of Answer
                    if ("3.14" in text):
                        if "ANSWER" not in events:
                            print(f"✅ ANSWER Detected from {source}: {text[:30]}...")
                            events.add("ANSWER")
                    
                    # 3. Final Conclusion (Brain Deep)
                    if "COORDINATION" in events and "ANSWER" in events:
                        if source == "Brain" and len(text.split()) > 20:
                            if "COMPLETION" not in events:
                                print(f"✅ COMPLETION Detected: {text[:30]}...")
                                events.add("COMPLETION")

        except asyncio.TimeoutError:
            pytest.fail(f"Flow timed out. Events captured: {events}")

        # Assert full flow
        assert "COORDINATION" in events, "Lab failed to coordinate agents."
        assert "ANSWER" in events, "Lab failed to provide the digits."
        assert "COMPLETION" in events, "Lab failed to conclude the interaction."

if __name__ == "__main__":
    asyncio.run(test_pi_to_20_digits_flow())
