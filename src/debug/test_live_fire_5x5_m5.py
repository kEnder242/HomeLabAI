import asyncio
import json
import time
import uuid
import sys
import os

sys.path.insert(0, '/home/jallred/Dev_Lab/HomeLabAI/src')
from logic.speculative_triage import resolve_active_deep_thought_target

QUERIES = [
    "What is the RAPL power instrumentation architecture in the lab?",
    "Explain the 18-year shift from fuser-kill to REST-sleep.",
    "How does the M5 Air handle 32k context reasoning vs RTX 4090?",
    "Review the PCIe RAS error burst detection methodology.",
    "Summarize the BKM protocol for SRE incident response."
]

async def run_5x5():
    print("=" * 70)
    print("🚀 SPRINT 67.0: 5x5 Deep Thought Multi-Seat Shakedown Gauntlet")
    print("=" * 70)

    # 1. Probe & Verify Target
    active_target = resolve_active_deep_thought_target()
    print(f"[*] Active Deep Thought Target: {active_target['name']} ({active_target['host']}:{active_target['port']} [{active_target['protocol']}])")
    assert active_target["name"] == "M5_AIR", f"Expected M5_AIR but got {active_target['name']}"

    # 2. Run 5 Turns
    success_count = 0
    for idx, q in enumerate(QUERIES, 1):
        print(f"\n--- [Turn {idx}/5] Query: '{q}' ---")
        t0 = time.time()
        
        # Test direct socket & API reachability for turn
        import urllib.request
        payload = {
            "model": "mlx-community--Qwen3.8-27B-4bit",
            "messages": [
                {"role": "system", "content": "You are Deep Thought. Answer with high technical density in 2 sentences."},
                {"role": "user", "content": q}
            ],
            "max_tokens": 150,
            "temperature": 0.2
        }
        
        req = urllib.request.Request(
            f"http://{active_target['host']}:{active_target['port']}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "AcmeLab/5.0"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content", "")
                elapsed = time.time() - t0
                toks = data.get("usage", {}).get("completion_tokens", len(text.split()))
                tp = round(toks / elapsed, 1) if elapsed > 0 else 0
                
                print(f"  ✅ [M5 AIR] TTFT & Decode ({elapsed:.2f}s | {toks} toks | {tp} tok/s):")
                print(f"     '{text.strip()[:160]}...'")
                success_count += 1
        except Exception as e:
            print(f"  ❌ [FAIL] Turn {idx} error: {e}")

    print("\n" + "=" * 70)
    print(f"🏆 5x5 SHAKEDOWN RESULT: {success_count}/5 Turns Successful on Apple M5 Air.")
    print("=" * 70)
    return success_count == 5

if __name__ == "__main__":
    ok = asyncio.run(run_5x5())
    sys.exit(0 if ok else 1)
