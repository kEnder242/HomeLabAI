import psutil
import socket
import subprocess
import os
import json

def audit():
    print("="*60)
    print("UNIFIED FAMILY AUDIT: PHYSICAL TRUTH")
    print("="*60)

    # 1. Ports
    ports = {8088: "vLLM", 11434: "Ollama", 8765: "Hub", 9999: "Attendant"}
    print("\n[PORTS]")
    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        res = sock.connect_ex(('127.0.0.1', port))
        status = "OPEN" if res == 0 else "CLOSED"
        print(f"  {port:<5} | {name:<10} | {status}")
        sock.close()

    # 2. VRAM
    print("\n[GPU SILICON]")
    try:
        smi = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"], text=True)
        print(f"  Active Compute: {smi.strip() or 'None'}")
    except:
        print("  Active Compute: ERROR")

    # 3. Ledger vs Reality
    print("\n[LEDGER]")
    ledger_path = "/home/jallred/Dev_Lab/HomeLabAI/run/active_pids.json"
    if os.path.exists(ledger_path):
        with open(ledger_path, 'r') as f:
            ledger = json.load(f)
            inventory = ledger.get("inventory", ledger)
            for key, val in inventory.items():
                if isinstance(val, int):
                    alive = psutil.pid_exists(val)
                    print(f"  {key:<12} | PID: {val:<8} | Alive: {alive}")
    else:
        print("  Ledger not found.")

    # 4. Crash Logs
    print("\n[FORENSIC TAIL]")
    for log in ["vllm_server.log", "server.log"]:
        log_path = f"/home/jallred/Dev_Lab/HomeLabAI/{log}"
        if os.path.exists(log_path):
            tail = subprocess.check_output(["tail", "-n", "3", log_path], text=True)
            print(f"  -- {log} --\n{tail.strip()}")

if __name__ == "__main__":
    audit()
