import requests
import json
import time

STYLE_KEY = "92e785ba"
ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "http://localhost:8765"

def study():
    print("--- 📚 Triage Stability Study ---")
    
    # 1. Ensure clean slate
    print("[1] Resetting Silicon...")
    requests.post(f"{ATTENDANT_URL}/reset_cache?key={STYLE_KEY}")
    time.sleep(2)
    print("[2] Sending Wake Signal...")
    requests.post(f"{ATTENDANT_URL}/wake?key={STYLE_KEY}")
    
    # Wait for recovery
    for i in range(60):
        time.sleep(2)
        status = requests.get(f"{ATTENDANT_URL}/status?key={STYLE_KEY}").json()
        if status.get("operational"):
            print("[WAKE]: Engine ready.")
            break
        print(f"[WAIT]: Waiting for engine... {i+1}/60")

    else:
        print("[FAIL]: Engine timed out.")
        return

    # 2. Test Cases
    queries = [
        "[ME] What is the RAPL BKM for thermal profiling?",
        "[ME] tell me about 2017",
        "[ME] hello"
    ]

    modes = ["WATERFALL", "POOLING"]
    
    results = []

    for mode in modes:
        print(f"\n--- Testing Mode: {mode} ---")
        # Toggle mode
        requests.post(f"{HUB_URL}/hub/config/streaming?key={STYLE_KEY}", json={"node": "lab", "mode": mode})
        
        for q in queries:
            print(f"[TEST]: {q}")
            
            from ai_engine_v2 import McpClient
            client = McpClient()
            # We filter for 'lab' source to get the Triage result
            res = client.generate(q, options={"target_source": "lab"})
            
            is_gibberish = "!!!" in res or len(res) < 10 or "{" not in res
            status = "✅ STABLE" if not is_gibberish else "❌ GIBBERISH"
            print(f"[RESULT]: {status}")
            print(f"[RAW]: {res[:100]}...")
            
            results.append({"mode": mode, "query": q, "status": status})
            time.sleep(2)

    print("\n--- FINAL RESULTS ---")
    for r in results:
        print(f"{r['mode']} | {r['status']} | {r['query']}")

if __name__ == "__main__":
    # Ensure src is in path for imports
    import sys
    import os
    sys.path.append(os.path.join(os.getcwd(), "HomeLabAI/src"))
    sys.path.append(os.path.join(os.getcwd(), "Portfolio_Dev/field_notes"))
    study()
