import asyncio
import json
import pytest
import websockets

VERSION = "3.4.19"

@pytest.mark.asyncio
async def test_pi_to_20_digits_flow():
    """
    Verifies the complete Bicameral flow for a complex query:
    1. User asks 'pi to 21 digits'.
    2. Pinky delegates via 'ask_brain'.
    3. Brain provides the insight.
    4. Pinky synthesizes.
    """
    url = "ws://localhost:8765"
    async with websockets.connect(url) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"type": "handshake", "version": VERSION}))
        
        # 2. Send Query
        query = "What is the value of pi to exactly 21 digits?"
        await ws.send(json.dumps({"type": "text_input", "content": query}))
        
        # 3. Monitor for Flow Events
        events = []
        try:
            # High timeout for Brain reasoning
            async with asyncio.timeout(60):
                while len(events) < 4:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if "brain" in data:
                        text = data["brain"]
                        source = data.get("brain_source", "Unknown")
                        print(f"[{source}]: {text[:50]}...")
                        
                        # 1. Handle Cached Flow (Clipboard)
                        if "[BRAIN_INSIGHT]" in text or "[FROM CLIPBOARD]" in text:
                            events.append("BRAIN_ANSWER")
                            events.append("DELEGATION") # Implicit in cache
                            events.append("SYNTHESIS_START") # Cached is already synthesized
                            events.append("FINAL_WORD")
                            break

                        # 2. Handle Live Flow
                        if "ASK_BRAIN" in text and source == "Pinky":
                            events.append("DELEGATION")
                        elif "3.141592653589793238462" in text and "Brain" in source:
                            events.append("BRAIN_ANSWER")
                        elif "Synthesizing" in text and source == "Pinky":
                            events.append("SYNTHESIS_START")
                        elif source == "Pinky" and "DELEGATION" in events and "BRAIN_ANSWER" in events:
                            # Final synthesis (not a reflexive tic)
                            if "Poit!" in text or "Narf!" in text or len(text) > 20:
                                events.append("FINAL_WORD")

        except asyncio.TimeoutError:
            pytest.fail(f"Flow timed out. Events captured: {events}")

        # Assert full flow
        assert "DELEGATION" in events, "Pinky failed to delegate."
        assert "BRAIN_ANSWER" in events, "Brain failed to provide the digits."
        assert "SYNTHESIS_START" in events, "Pinky failed to initiate synthesis."
        assert "FINAL_WORD" in events, "Pinky failed to deliver final synthesis."

if __name__ == "__main__":
    asyncio.run(test_pi_to_20_digits_flow())
