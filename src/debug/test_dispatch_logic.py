import json
import re

def execute_dispatch_mock(raw_text):
    """Hardened Dispatcher Logic: Multi-layer JSON extraction."""
    try:
        # 1. Greedy search for the largest possible JSON block
        match = re.search(r'(\{.*\})', raw_text, re.DOTALL | re.MULTILINE)
        if not match:
            return {"type": "text", "content": raw_text}

        json_str = match.group(1)
        
        # 2. Recursive Parsing (for nested or concatenated JSON)
        try:
            data = json.loads(json_str)
            tool = data.get("tool")
            
            if not tool and "reply_to_user" in data:
                return {"type": "text", "content": data["reply_to_user"]}
            
            if tool:
                params = data.get("parameters") or {}
                if isinstance(params, str): params = {"text": params}
                return {"type": "tool", "tool": tool, "params": params}
            
            # If valid JSON but no tool, return as text
            return {"type": "text", "content": raw_text}

        except json.JSONDecodeError:
            # 3. Fallback: If greedy failed, try non-greedy search for smaller blocks
            matches = re.findall(r'(\{.*?\})', raw_text, re.DOTALL)
            for m in matches:
                try:
                    d = json.loads(m)
                    if d.get("tool"):
                        return {"type": "tool", "tool": d.get("tool"), "params": d.get("parameters") or {}}
                except: continue
            
            return {"type": "text", "content": raw_text}

    except Exception as e:
        return {"type": "error", "message": str(e)}

# --- TEST SUITE ---
def test():
    cases = [
        ("Hello { not json }", "text"),
        ("Call this: { \"tool\": \"ask_brain\", \"parameters\": {\"task\": \"pi\"} }", "tool"),
        ("Result: { \"reply_to_user\": \"Narf!\" }", "text"),
        ("Empty: { \"tool\": null }", "text"),
        ("Distractor: { \"decision\": \"unknown\" } { \"tool\": \"close_lab\" }", "tool")
    ]

    for input_txt, expected in cases:
        res = execute_dispatch_mock(input_txt)
        print(f"Input: {input_txt[:20]} -> Result: {res['type']}")
        assert res['type'] == expected

if __name__ == "__main__":
    test()
    print("\n[PASS] Dispatch Logic Hardened (v4).")
