import asyncio
import subprocess
import aiohttp
import time
import os

# Configuration from Environment or Defaults
ATTENDANT_URL = os.environ.get("ATTENDANT_URL", "http://localhost:9999")

def get_gpu_info():
    """Returns (used, total) MiB."""
    try:
        cmd = [
            "nvidia-smi", "--query-gpu=memory.used,memory.total", 
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd).decode().strip()
        used, total = map(int, output.split(','))
        return used, total
    except Exception:
        return 0, 0

async def run_apollo_live():
    print("--- 🚀 Apollo 11: Real-Time Silicon Measurement (Generic) ---")
    
    # 1. Hardware Detection
    used_base, total_cap = get_gpu_info()
    if total_cap == 0:
        print("[ERROR] No NVIDIA GPU detected. Aborting.")
        return

    print(f"[APOLLO] Detected GPU Capacity: {total_cap} MiB")
    print(f"[APOLLO] Baseline VRAM: {used_base} MiB")
    
    # 2. Trigger Start via Attendant
    async with aiohttp.ClientSession() as session:
        print("[APOLLO] Launching Full Stack (vLLM + Ears)...")
        # Note: Attendant v3.6.2 manages vLLM internally
        try:
            await session.post(
                f"{ATTENDANT_URL}/start", 
                json={"engine": "vLLM", "disable_ear": False}
            )
        except Exception as e:
            print(f"[ERROR] Could not connect to Attendant: {e}")
            return
        
        start_time = time.time()
        max_vram = used_base
        
        # 120s timeout for load
        while time.time() - start_time < 120:
            current, _ = get_gpu_info()
            if current > max_vram:
                max_vram = current
            
            try:
                resp = await session.get(f"{ATTENDANT_URL}/status")
                status = await resp.json()
                
                if status.get("full_lab_ready"):
                    print("\n[APOLLO] Lab is READY.")
                    break
                
                if status.get("last_error"):
                    print(f"\n[APOLLO] FAILURE DETECTED: {status['last_error']}")
                    break
            except Exception:
                pass
            
            print(
                f"\r[APOLLO] Current VRAM: {current:>5} MiB | Peak: {max_vram:>5} MiB", 
                end="", flush=True
            )
            await asyncio.sleep(2)
            
        print(f"\n[APOLLO] Final Peak: {max_vram} MiB")
        print(f"[APOLLO] Budget: {max_vram} / {total_cap} MiB ({(max_vram/total_cap)*100:.1f}%)")
        
        # 95% threshold for generic safety
        if max_vram > total_cap * 0.95:
            print("[CRITICAL] REDLINE. Ears or context will likely OOM.")
        else:
            print("[NOMINAL] Silicon headroom verified.")

if __name__ == "__main__":
    asyncio.run(run_apollo_live())
