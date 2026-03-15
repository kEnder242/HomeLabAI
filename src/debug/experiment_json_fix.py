import json
import re

samples = [
    # Sample 1: The "Domain List" error (The most common failure)
    """{
  "intent": "STRATEGIC",
  "domain": "exp_tlm", "exp_bkm", "exp_for", "standard",
  "situation": "[STRATEGIC_ANCHOR]",
  "hints": "None"
}""",
    # Sample 2: Truncated output
    """{
  "intent": "STRATEGIC",
  "domain": "exp_tlm",
  "exp_bkm": "ESB2",
  "exp_for": "DCMI",
  "situation": "Mastery of Firmware Development and Transport Library Creation",""",
    # Sample 3: Double braces
    """{{
  "intent": "STRATEGIC",
  "domain": "standard",
  "situation": "[UNKNOWN]",
  "hints": "Proceed with caution."
}}""",
    # Sample 4: Model chatter wrapped JSON
    """Here is the situational triage:
{
  "intent": "STRATEGIC",
  "domain": "exp_tlm",
  "situation": "[TEST]",
  "hints": "Test"
}
Hope this helps!"""
]

def experimental_clean(text):
    print(f"\n--- Processing Raw ---\n{text}")
    
    # 1. Recursive/Inner block finding
    # We want to find anything between { and }
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        clean = match.group(1)
    else:
        # If no closing brace, try to find the last valid comma or property and close it
        # (This is for the truncated sample 2)
        if "{" in text:
            clean = text[text.find("{"):] + '\n  "error": "truncated"\n}'
        else:
            return None

    # 2. Fix the "Domain List" artifact: "key": "val1", "val2", ... -> "key": "val1"
    # Improved regex: Match the key and first value, then non-greedily match following comma-separated strings
    # until we hit something that looks like a new key (followed by :) or the end of the object.
    clean = re.sub(r'("domain":\s*"[^"]+")((?:,\s*"[^"]+")+)(?=\s*,|\s*\})', r'\1', clean)
    # Clean up trailing comma before closing brace
    clean = re.sub(r',\s*\}', r'\n}', clean)

    # 3. Double brace reduction
    clean = clean.replace("{{", "{").replace("}}", "}")
    
    # 4. Final attempt to parse
    try:
        data = json.loads(clean)
        print(f"SUCCESS: {data}")
        return data
    except json.JSONDecodeError as e:
        print(f"FAILED: {e}")
        # Secondary "Brute Force" for the domain list if regex 1 failed
        # Split by lines and discard lines that don't look like JSON properties
        lines = clean.split('\n')
        fixed_lines = []
        for line in lines:
            if ":" in line or "{" in line or "}" in line:
                # If a line has multiple values like Sample 1: "domain": "a", "b", "c"
                if line.count('"') > 4 and ":" in line:
                    parts = line.split(':')
                    key = parts[0]
                    first_val = parts[1].split(',')[0]
                    fixed_lines.append(f"{key}: {first_val},")
                else:
                    fixed_lines.append(line)
        
        brute_clean = "\n".join(fixed_lines)
        brute_clean = re.sub(r',\s*\}', r'\n}', brute_clean)
        try:
            data = json.loads(brute_clean)
            print(f"BRUTE SUCCESS: {data}")
            return data
        except Exception as e2:
            print(f"BRUTE FAILED: {e2}")
            return None

if __name__ == "__main__":
    for s in samples:
        experimental_clean(s)
