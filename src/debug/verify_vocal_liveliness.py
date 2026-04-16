import asyncio
import aiohttp
import json
import sys
import time

# --- Paths ---
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "none"

async def verify_vocal():
    print("[*] Performing Physician's Final Assertion (Cognitive Truth check)...")
    url = "http://127.0.0.1:8765/hub"
    key = get_key()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"{url}?key={key}", timeout=5.0) as ws:
                # 1. Handshake
                await ws.send_json({"type": "handshake", "client": "validator", "version": "1.0"})
                
                # 2. Functional Probe
                payload = {"type": "text_input", "content": "[ME] [INTERNAL] Physician's Larynx Probe. Respond with SUCCESS."}
                await ws.send_json(payload)
                
                # 3. Await Success (30s timeout for kernel residency)
                start_t = time.time()
                while time.time() - start_t < 30:
                    msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        text = data.get("text", "").upper()
                        if "SUCCESS" in text or "OPERATIONAL" in text:
                            print("[+] VOCAL TRUTH VERIFIED: Lab answered correctly.")
                            await ws.close()
                            return True
                
                print("[-] VOCAL TRUTH FAILURE: Lab is silent or incoherent.")
                return False
    except Exception as e:
        print(f"[-] VOCAL TRUTH FAILURE: Connection error: {e}")
        return False

if __name__ == "__main__":
    if asyncio.run(verify_vocal()):
        sys.exit(0)
    else:
        sys.exit(1)
