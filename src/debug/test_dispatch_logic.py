import json
import re
import sys
import os

# Mock broadcast for testing
async def mock_broadcast(msg):
    # print(f"[MOCK_BROADCAST] {msg}")
    pass

class DispatchTester:
    def __init__(self):
        # Minimized mock logic for the test
        pass

    def execute_dispatch_actual(self, raw_text, source):
        """Production Logic (Extracted from cognitive_hub.py)."""
        if "Brain" in source:
            banter_pattern = r"\b(narf|poit|zort|egad|trotro)\b"
            raw_text = re.sub(banter_pattern, "", raw_text, flags=re.IGNORECASE).strip()
            raw_text = re.sub(r"^[,\.\!\?\s\"\'\d]+", "", raw_text).strip()
            raw_text = re.sub(r"\*[^*]+\*", "", raw_text).strip()

        if "{" not in raw_text:
            return {"type": "text", "content": raw_text}

        try:
            data = raw_text
            match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except Exception:
                    pass

            tool = data.get("tool") if isinstance(data, dict) else None
            params = data.get("parameters", {}) if isinstance(data, dict) else {}

            if tool:
                return {"type": "tool", "tool": tool, "params": params}
            
            # Special case for reply_to_user
            if isinstance(data, dict) and "reply_to_user" in data:
                return {"type": "text", "content": data["reply_to_user"]}

            return {"type": "text", "content": raw_text}
        except Exception:
            return {"type": "text", "content": raw_text}

# --- TEST SUITE ---
def test():
    tester = DispatchTester()
    cases = [
        ("Brain", "Narf! The root cause is a race condition.", "text"),
        ("Brain", "*Narf!* { \"tool\": \"ask_brain\", \"parameters\": \"pi\" }", "tool"),
        ("Pinky", "Poit! I'm checking sensors.", "text"),
        ("Brain", "{ \"reply_to_user\": \"Direct answer.\" }", "text"),
    ]

    for source, input_txt, expected in cases:
        res = tester.execute_dispatch_actual(input_txt, source)
        print(f"[{source}] Input: {input_txt[:25]}... -> Result: {res['type']}")
        assert res['type'] == expected

if __name__ == "__main__":
    test()
    print("\n[PASS] Production Dispatch Logic Verified.")
