import asyncio
import subprocess
import aiohttp
import time

ATTENDANT_URL = "http://localhost:9999"

def get_vram():
    cmd = ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]
    return int(subprocess.check_output(cmd).decode().strip())

async def run_apollo_live():
    print("--- 🚀 Apollo 11: Real-Time Silicon Measurement ---")
    
    # 1. Baseline
    baseline = get_vram()
    print(f"[APOLLO] Baseline VRAM: {baseline} MiB")
    
    # 2. Trigger Start via Attendant
    async with aiohttp.ClientSession() as session:
        print("[APOLLO] Launching Full Stack (vLLM 0.4 + Ears)...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "vLLM", "disable_ear": False})
        
        start_time = time.time()
        max_vram = baseline
        
        while time.time() - start_time < 120:
            current = get_vram()
            if current > max_vram: max_vram = current
            
            resp = await session.get(f"{ATTENDANT_URL}/status")
            status = await resp.json()
            
            if status["full_lab_ready"]:
                print("\n[APOLLO] Lab is READY.")
                break
            
            print(f"\r[APOLLO] Current VRAM: {current:>5} MiB | Peak: {max_vram:>5} MiB", end="")
            await asyncio.sleep(2)
            
        print(f"\n[APOLLO] Final Peak: {max_vram} MiB")
        capacity = 10800
        print(f"[APOLLO] Budget: {max_vram} / {capacity} MiB ({(max_vram/capacity)*100:.1f}%)")
        
        if max_vram > 10000:
            print("[CRITICAL] REDLINE. Ears will fail.")
        else:
            print("[NOMINAL] Headroom verified.")

if __name__ == "__main__":
    asyncio.run(run_apollo_live())
