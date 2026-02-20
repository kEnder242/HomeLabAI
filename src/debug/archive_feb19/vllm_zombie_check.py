import os
import time
import psutil
import subprocess
import sys

VLLM_LOG = "HomeLabAI/vllm_server.log"

def get_vram_usage():
    try:
        res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
        return int(res.decode().strip())
    except:
        return 0

def check_zombie():
    print("--- 🧟 VLLM ZOMBIE SENTINEL ---")
    
    # 1. Process Check
    vllm_proc = None
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'vllm' in ' '.join(proc.info['cmdline'] or []).lower():
            vllm_proc = proc
            break
            
    if not vllm_proc:
        print("❌ STATUS: vLLM not running.")
        return False

    print(f"✅ Process Detected (PID: {vllm_proc.pid})")

    # 2. Log Stagnation Check
    if not os.path.exists(VLLM_LOG):
        print("❌ STATUS: Log file missing.")
        return False
        
    initial_mtime = os.path.getmtime(VLLM_LOG)
    print("[WAIT] Monitoring log for 15s...")
    time.sleep(15)
    
    if os.path.getmtime(VLLM_LOG) == initial_mtime:
        log_stalled = True
        print("⚠️  LOG STALLED: No updates in 15s.")
    else:
        log_stalled = False
        print("✅ LOG ACTIVE: Updates detected.")

    # 3. VRAM Triangulation
    vram = get_vram_usage()
    print(f"📊 VRAM Usage: {vram}MiB")
    
    # Logic: If process is running and log is stalled, but VRAM is low (< 1000MiB), it's a weight-loading deadlock.
    if log_stalled and vram < 1000:
        print("‼️  ZOMBIE DETECTED: Engine has deadlocked during weight loading.")
        return True
    elif log_stalled:
        print("⚠️  POTENTIAL ZOMBIE: Engine is silent but holding memory. Might be warming up.")
    else:
        print("✨ STATUS: Engine appears healthy.")
        
    return False

if __name__ == "__main__":
    is_zombie = check_zombie()
    sys.exit(1 if is_zombie else 0)
