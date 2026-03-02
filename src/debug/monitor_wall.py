import time
import subprocess
import os

LOG_FILE = "/home/jallred/Dev_Lab/HomeLabAI/vllm_016_bench.log"
WALL_MIB = 333

def get_vram():
    try:
        cmd = "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        return int(output)
    except Exception:
        return 0

def monitor():
    print(f"--- 🩺 Forensic Watcher: Target {WALL_MIB}MiB ---")
    start_time = time.time()
    last_vram = 0
    
    while True:
        vram = get_vram()
        elapsed = int(time.time() - start_time)
        
        if vram != last_vram:
            status = "STALLED" if vram == WALL_MIB else "PROGRESSING"
            print(f"[{elapsed}s] VRAM: {vram}MiB | Status: {status}")
            last_vram = vram
            
            if vram > 400:
                print(f"\n[!!!] BREAKTHROUGH: VRAM ({vram}MiB) has passed the 333MiB wall!")
                return True
        
        # Check if log shows error
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f:
                    content = f.read()
                    if "Error" in content or "Traceback" in content:
                        # Only report if it's a recent error to avoid stale log noise
                        print("\n[FAIL] Error detected in logs.")
                        return False
            except Exception:
                pass
        
        if elapsed > 300:
            print("\n[TIMEOUT] 5 minutes elapsed without breakthrough.")
            return False
            
        time.sleep(2)

if __name__ == "__main__":
    monitor()
