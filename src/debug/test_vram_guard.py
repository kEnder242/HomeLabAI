import time
import subprocess
import os
import sys
import requests

# --- Path Self-Awareness ---
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_LAB_ROOT = os.path.abspath(os.path.join(_SELF_DIR, "..", ".."))
_VLLM_LOG = os.path.join(_LAB_ROOT, "vllm_server.log")

ATTENDANT_URL = "http://localhost:9999"
VLLM_URL = "http://localhost:8088/v1/chat/completions"
WALL_MIB = 333

def get_vram():
    """Direct query to nvidia-smi for physical truth."""
    try:
        cmd = "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        return int(output)
    except Exception:
        return 0

def check_inference():
    """Verify that VRAM usage represents living weights by performing a ping."""
    try:
        payload = {
            "model": "unified-base",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        r = requests.post(VLLM_URL, json=payload, timeout=2)
        return r.status_code == 200
    except:
        return False

def audit_gate():
    print(f"--- 🩺 Silicon Wall Audit: vLLM 0.17 Stability ---")
    start_time = time.time()
    last_vram = 0
    passed_wall = False
    
    while True:
        vram = get_vram()
        elapsed = int(time.time() - start_time)
        
        if vram != last_vram:
            status = "STALLED (333MiB Trap)" if vram == WALL_MIB else "LOADING"
            if vram > 400: status = "RESIDENT"
            
            print(f"[{elapsed}s] VRAM: {vram}MiB | Status: {status}")
            last_vram = vram
            
            if vram > 400 and not passed_wall:
                print(f"[!!!] BREAKTHROUGH: VRAM has passed the {WALL_MIB}MiB wall.")
                passed_wall = True
        
        # Check logs for JIT or OOM errors
        if os.path.exists(_VLLM_LOG):
            try:
                with open(_VLLM_LOG, 'r') as f:
                    content = f.read()[-2000:] # Last 2k chars
                    if "RuntimeError" in content or "ValueError" in content:
                        print("\n[FAIL] Fatal engine error detected in logs.")
                        return False
            except Exception: pass
        
        # Final Verification Gate
        if passed_wall:
            if check_inference():
                print(f"[SUCCESS] Engine is reasoning at {vram}MiB.")
                return True
        
        if elapsed > 180:
            print("\n[TIMEOUT] Ignition took too long (>3m).")
            return False
            
        time.sleep(5)

if __name__ == "__main__":
    success = audit_gate()
    sys.exit(0 if success else 1)
