import asyncio
import aiohttp
import time
import sys
import subprocess
import json

# --- Paths ---
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "none"

async def flood_intercom(target_url, count=30):
    print(f"[*] Starting Intercom Flood: {count} bursts to {target_url}")
    key = get_key()
    
    # 0. Get initial Hub PID
    try:
        fuser_out = subprocess.check_output(["sudo", "fuser", "8765/tcp"], stderr=subprocess.STDOUT, text=True)
        initial_pid = int(fuser_out.split(":")[-1].strip())
        print(f"[*] Initial Hub PID detected: {initial_pid}")
    except:
        print("[!] Hub is currently offline. Starting Lab...")
        subprocess.run(["curl", "-X", "POST", f"http://localhost:9999/start?key={key}", "-H", "Content-Type: application/json", "-d", '{"engine": "OLLAMA", "model": "MEDIUM"}'])
        await asyncio.sleep(10)
        fuser_out = subprocess.check_output(["sudo", "fuser", "8765/tcp"], text=True)
        initial_pid = int(fuser_out.split(":")[-1].strip())

    tasks = []
    
    async def single_burst(i):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"{target_url}?key={key}", timeout=5.0) as ws:
                    # Send a quick query
                    await ws.send_json({"type": "text_input", "content": f"[ME] Flood probe {i}"})
                    # Wait for a heartbeat or quip
                    msg = await asyncio.wait_for(ws.receive(), timeout=3.0)
                    await ws.close()
            return True
        except Exception as e:
            return False

    start_t = time.time()
    for i in range(count):
        tasks.append(single_burst(i))
        # 100ms interval between connections
        await asyncio.sleep(0.1)
    
    results = await asyncio.gather(*tasks)
    end_t = time.time()
    
    successes = sum(1 for r in results if r)
    
    # 4. Final PID Check
    try:
        fuser_final = subprocess.check_output(["sudo", "fuser", "8765/tcp"], stderr=subprocess.STDOUT, text=True)
        final_pid = int(fuser_final.split(":")[-1].strip())
    except:
        final_pid = 0

    print(f"\n[!] Flood Complete in {end_t - start_t:.2f}s")
    print(f"[!] Success Rate: {successes}/{count} ({successes/count*100:.1f}%)")
    
    if final_pid != initial_pid:
        print(f"[!] CRITICAL FAILURE: Hub PID changed from {initial_pid} to {final_pid} during load.")
        print("[!] The Watchdog reaped the foyer during active traffic.")
        return False
    
    if successes < count * 0.8:
        print("[!] FAILURE: Success rate too low. Intercom is 'trash'.")
        return False

    print("[+] PASS: System is stable under burst load.")
    return True

if __name__ == "__main__":
    url = "http://127.0.0.1:8765/hub"
    asyncio.run(flood_intercom(url))
