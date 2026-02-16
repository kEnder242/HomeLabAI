import subprocess
import sys
import os
import requests
import time

def run_gate():
    print("--- 🚪 Full-Stack Smoke Gate (Simple) ---")
    
    # 1. Check vLLM dependency
    try:
        r = requests.get("http://localhost:8088/v1/models", timeout=5)
        if r.status_code != 200:
            print("❌ vLLM not ready (8088).")
            return False
        print("✅ vLLM engine detected.")
    except Exception:
        print("❌ vLLM engine unreachable on 8088.")
        return False

    # 2. Port Cleanup (Ensure 8765 is free)
    subprocess.run("pkill -f acme_lab.py", shell=True)
    time.sleep(1)

    # 3. Execute Server in Smoke Mode
    print("[RUN] acme_lab.py --mode DEBUG_SMOKE")
    env = os.environ.copy()
    # Add src to path for node imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(script_dir)
    env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{src_dir}"
    
    try:
        # Use the absolute path to the venv python
        python_bin = os.path.join(os.path.dirname(src_dir), ".venv/bin/python3")
        lab_script = os.path.join(src_dir, "acme_lab.py")
        
        # This will block until self-termination (triggered by DEBUG_SMOKE logic)
        res = subprocess.run([
            python_bin, lab_script, 
            "--mode", "DEBUG_SMOKE", 
            "--disable-ear"
        ], env=env, capture_output=True, text=True, timeout=60, cwd=os.path.dirname(src_dir))
        
        if res.returncode == 0:
            print("✅ Server reached READY and exited cleanly.")
            # Print the last few lines of log to confirm
            print("\n--- SERVER LOG TAIL ---")
            tail = "\n".join(res.stderr.splitlines()[-10:])
            print(tail)
            print("--- END LOG ---")
            return True
        else:
            print(f"❌ Server failed with code {res.returncode}")
            print("\n--- ERROR OUTPUT ---")
            print(res.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Server hung (timed out after 60s).")
        return False
    except Exception as e:
        print(f"❌ Execution error: {e}")
        return False

if __name__ == "__main__":
    if run_gate():
        print("\n--- ✨ SMOKE GATE PASSED ---")
        sys.exit(0)
    else:
        print("\n--- ❌ SMOKE GATE FAILED ---")
        sys.exit(1)
