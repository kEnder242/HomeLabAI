import os
import subprocess
import sys
import time

import requests

LOG_FILE = "/home/jallred/Dev_Lab/HomeLabAI/logs/native_canary_550.log"
API_URL = "http://localhost:8088/v1/models"


def get_vram():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]
        )
        return int(out.decode().strip())
    except Exception:
        return 0


def get_log_size():
    if os.path.exists(LOG_FILE):
        return os.path.getsize(LOG_FILE)
    return 0


print("--- 🕵️ LONG-BURN HANDSHAKE MONITOR ---")
print(f"Targeting: {API_URL}")
print("Duration: 10 minutes (20 cycles of 30s)")

start_vram = get_vram()
start_time = time.time()
vram_delta = 0

for i in range(1, 21):
    time.sleep(30)
    current_vram = get_vram()
    vram_delta = current_vram - start_vram
    log_size = get_log_size()

    # Try API
    status = "OFFLINE"
    try:
        r = requests.get(API_URL, timeout=2)
        if r.status_code == 200:
            status = "✨ ONLINE!"
            print(f"\n[CYCLE {i}] {status} - vLLM has responded!")
            sys.exit(0)
    except Exception:
        pass

    print(
        f"[CYCLE {i}] Time: {int(time.time() - start_time)}s | VRAM: {current_vram}MiB (Delta: {vram_delta}MiB) | Log: {log_size} bytes | API: {status}"
    )

print("\n‼️  LONG-BURN TIMEOUT: No response from API after 10 minutes.")
if vram_delta == 0:
    print("💀 DEADLOCK CONFIRMED: VRAM never changed.")
else:
    print(f"🤔 UNKNOWN STATE: VRAM grew by {vram_delta}MiB but API never responded.")
sys.exit(1)
