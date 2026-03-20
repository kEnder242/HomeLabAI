import asyncio
import json
import logging
import re

class MockHub:
    def __init__(self):
        self.current_fuel = 0.5
        self.current_topic = "Casual"
        self.broadcasts = []

    def bridge_signal_clean(self, text):
        if "{" not in text: return None
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        return match.group(1) if match else None

    async def _dispatch_plain_text(self, text, source, is_internal, final=True):
        self.broadcasts.append({"text": text, "source": source, "final": final})
        return text

    async def broadcast(self, data):
        self.broadcasts.append(data)

    async def execute_dispatch(self, text, source, final=True):
        clean_text = text.strip()
        json_block = self.bridge_signal_clean(clean_text)
        
        if json_block:
            try:
                # FIXED GATE
                is_tool = any(k in json_block for k in ['"tool"', '"reply_to_user"', '"facilitate"', '"handle_myself"', '"ask_brain"'])
                
                if not is_tool:
                    pass 
                else:
                    data = json.loads(json_block)
                    tool = data.get("tool")
                    params = data.get("parameters", {})
                    
                    if tool == "ask_brain":
                        self.current_fuel = 1.0
                        return "PROMOTED"
                    elif tool == "handle_myself":
                        self.current_fuel = 0.0
                        # FIXED ROBUSTNESS
                        quip = params.get("quip")
                        if not quip:
                            for val in params.values():
                                if isinstance(val, str):
                                    quip = val
                                    break
                        quip = quip or "Narf! I'll take this one."
                        return await self._dispatch_plain_text(quip, source, False, final=final)
            except Exception as e:
                print(f"Error: {e}")

        return await self._dispatch_plain_text(clean_text, source, False, final=final)

async def test_reproduction():
    hub = MockHub()
    # Case 1: The 'hi' query with 'kwargs' hallucination
    raw_response = '{"tool": "handle_myself", "parameters": {"kwargs": "hi"}}'
    print(f"Testing raw response: {raw_response}")
    await hub.execute_dispatch(raw_response, "Pinky (Triage)")
    
    last_msg = hub.broadcasts[-1]
    print(f"Resulting message: {last_msg.get('text')}")
    
    if last_msg.get('text') == "hi":
        print("✅ SUCCESS: Tool call was intercepted and quip extracted.")
    else:
        print("❌ FAILURE: Raw JSON leaked or wrong text returned.")

if __name__ == "__main__":
    asyncio.run(test_reproduction())
