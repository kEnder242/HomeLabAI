import json
import re

def execute_dispatch_mock(raw_text):
    """Hardened Dispatcher Logic (v5): Character-level JSON discovery."""
    try:
        # 1. Find the first '{' and last '}'
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        
        if start == -1 or end == -1 or end < start:
            return {"type": "text", "content": raw_text}

        # 2. Extract potential JSON
        potential_json = raw_text[start:end+1]
        
        # 3. Defensive Parsing
        try:
            data = json.loads(potential_json)
            tool = data.get("tool")
            
            # Special case: 'reply_to_user' as a key
            if not tool and "reply_to_user" in data:
                return {"type": "text", "content": data["reply_to_user"]}
            
            if tool:
                params = data.get("parameters") or {}
                if isinstance(params, str): params = {"text": params}
                return {"type": "tool", "tool": tool, "params": params}
            
            # If valid JSON but no recognized tool key, treat as text
            return {"type": "text", "content": raw_text}

        except json.JSONDecodeError:
            # 4. Fallback: If outer block is invalid, try findall for smaller valid objects
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
        ("pinky.None", "text"), # No braces
        ("pinky: { \"tool\": \"ask_brain\", \"parameters\": \"pi\" }", "tool"),
        ("distractor { \"tool\": \"close_lab\" } suffix", "tool"),
        ("{ \"reply_to_user\": \"Narf!\" }", "text"),
        ("invalid { block } { \"tool\": \"list_cabinet\" }", "tool")
    ]

    for input_txt, expected in cases:
        res = execute_dispatch_mock(input_txt)
        print(f"Input: {input_txt[:20]} -> Result: {res['type']}")
        assert res['type'] == expected

if __name__ == "__main__":
    test()
    print("\n[PASS] Dispatch Logic Hardened (v5).")
