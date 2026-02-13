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
    url = "ws://localhost:8765"
    async with websockets.connect(url) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake", "version": VERSION}))
        # Consume handshake response
        await ws.recv() # status
        await ws.recv() # cabinet

        # 2. Send Query
        query = "What is the value of pi to exactly 21 digits?"
        await ws.send(json.dumps({"type": "text_input", "content": query}))

        # 3. Monitor for Flow Events
        events = []
        try:
            # High timeout for Brain reasoning
            async with asyncio.timeout(60):
                while len(events) < 3: # Delegation, Answer, and at least one Banter
                    msg = await ws.recv()
                    data = json.loads(msg)

                    if "brain" in data:
                        text = data["brain"]
                        source = data.get("brain_source", "Unknown")
                        print(f"[{source}]: {text[:50]}...")

                        # 1. Handle Cached Flow (Clipboard)
                        if "[CLIPBOARD]" in text:
                            events.append("DELEGATION")
                            events.append("BRAIN_ANSWER")
                            events.append("FINAL_WORD")
                            break

                        # 2. Handle Live Flow
                        if "ASK_BRAIN" in text and source == "Pinky":
                            events.append("DELEGATION")
                        elif "3.141592653589793238462" in text and "Brain" in source:
                            events.append("BRAIN_ANSWER")
                        elif source == "Pinky" and "DELEGATION" in events and "BRAIN_ANSWER" in events:
                            # Final synthesis or Banter
                            events.append("FINAL_WORD")

        except asyncio.timeoutError:
            pytest.fail(f"Flow timed out. Events captured: {events}")

        # Assert full flow
        assert "DELEGATION" in events, "Pinky failed to delegate."
        assert "BRAIN_ANSWER" in events, "Brain failed to provide the digits."
        assert "FINAL_WORD" in events, "Mind failed to conclude the interaction."

if __name__ == "__main__":
    asyncio.run(test_pi_to_20_digits_flow())
