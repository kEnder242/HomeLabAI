import subprocess
import time
import os
import gc
import sys
import psutil

def spawn_and_lose_reference():
    print("[DEBUG] Spawning child process (sleep 300)...")
    # Simulate start_vllm.sh backgrounding behavior
    # We use a long-lived process to see if it survives the parent reference loss
    proc = subprocess.Popen(
        ["sleep", "300"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    pid = proc.pid
    print(f"[DEBUG] Child spawned with PID: {pid}")
    return pid

def test_trap():
    print("--- [GC TRAP TEST] ---")
    child_pid = spawn_and_lose_reference()
    
    # Verify child is alive
    if psutil.pid_exists(child_pid):
        print(f"[VERIFY] Child {child_pid} is ALIVE.")
    else:
        print(f"[ERROR] Child {child_pid} failed to spawn.")
        return

    print("[DEBUG] Forcing garbage collection...")
    gc.collect()
    time.sleep(2)

    # Check if process is still responsive/resident
    if psutil.pid_exists(child_pid):
        print(f"[RESULT] SUCCESS: Child {child_pid} survived GC.")
    else:
        print(f"[RESULT] FATAL: Child {child_pid} REAPED BY GC.")

    # Cleanup
    try:
        os.kill(child_pid, 15)
        print("[DEBUG] Test cleanup complete.")
    except:
        pass

if __name__ == "__main__":
    test_trap()
