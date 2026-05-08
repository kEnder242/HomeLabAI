import requests
import json
import time
import os
import sys

ATTENDANT_URL = "http://localhost:9999"
HUB_URL = "http://localhost:8765"
STYLE_KEY = "92e785ba"

def clear_cache():
    print("🧹 Clearing GPU and Engine caches...")
    try:
        r = requests.post(f"{ATTENDANT_URL}/reset_cache?key={STYLE_KEY}", timeout=10)
        print(f"[RESULT]: {r.json().get('message')}")
    except Exception as e:
        print(f"[ERROR]: {e}")

def update_prompt(node, prompt):
    print(f"📝 Updating prompt for {node}...")
    try:
        payload = {"node": node, "prompt": prompt}
        r = requests.post(f"{ATTENDANT_URL}/update_prompt?key={STYLE_KEY}", json=payload, timeout=10)
        print(f"[RESULT]: {r.json().get('status')}")
    except Exception as e:
        print(f"[ERROR]: {e}")

def toggle_streaming(node, mode):
    print(f"🌊 Setting {node} to {mode}...")
    try:
        payload = {"node": node, "mode": mode}
        r = requests.post(f"{HUB_URL}/hub/config/streaming?key={STYLE_KEY}", json=payload, timeout=10)
        print(f"[RESULT]: {r.json().get('status')}")
    except Exception as e:
        print(f"[ERROR]: {e}")

def run_triage(query):
    print(f"🧠 Triggering Triage for: {query}")
    import asyncio
    import websockets

    async def _call():
        uri = "ws://localhost:8765"
        try:
            async with websockets.connect(uri) as ws:
                # Handshake
                await ws.send(json.dumps({"type": "handshake", "client": "triage_harness"}))
                
                # Send Query
                payload = {"type": "text_input", "content": query}
                await ws.send(json.dumps(payload))
                
                print("\n--- [LIVE OUTPUT] ---")
                full_raw = ""
                start_t = time.time()
                while time.time() - start_t < 60:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(msg)
                        
                        # Show EVERYTHING for transparency
                        source = data.get("brain_source", data.get("source", "System"))
                        content = data.get("brain", data.get("text", ""))
                        
                        if content:
                            print(f"[{source}]: {content}")
                            if "Triage" in source:
                                full_raw += content
                        
                        if data.get("final") == True or "[HUB] Triage successful" in str(data):
                            break
                    except asyncio.TimeoutError:
                        continue
                print("--- [END OUTPUT] ---\n")
                return full_raw
        except Exception as e:
            print(f"[WS ERROR]: {e}")
            return ""

    return asyncio.run(_call())

def main():
    print("=== 🩺 PHYSICIAN'S TRIAGE HARNESS ===")
    print("Commands: 'clear', 'prompt <text>', 'stream <WATERFALL|POOLING>', 'test <query>', 'quit'")
    
    current_prompt = "You are The Lab Node sentinel. Respond ONLY with a raw JSON block."
    
    while True:
        try:
            cmd_line = input("\n🩺 > ").strip()
            if not cmd_line: continue
            
            parts = cmd_line.split(' ', 1)
            cmd = parts[0].lower()
            
            if cmd == 'quit': break
            elif cmd == 'clear': clear_cache()
            elif cmd == 'prompt':
                if len(parts) > 1:
                    current_prompt = parts[1]
                    update_prompt("lab", current_prompt)
                else:
                    print(f"Current Lab Prompt: {current_prompt}")
            elif cmd == 'stream':
                if len(parts) > 1:
                    toggle_streaming("lab", parts[1].upper())
                else:
                    print("Usage: stream WATERFALL|POOLING")
            elif cmd == 'test':
                query = parts[1] if len(parts) > 1 else "[ME] hello"
                run_triage(query)
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
