import asyncio
import os
import sys
import subprocess

# V5 Transition Shim
# [FEAT-265] Waking State Machine (Orchestrator)

# [FEAT-122] Kernel-Level Visibility
try:
    import setproctitle
    setproctitle.setproctitle("acme_hub_v5")
except ImportError:
    pass

LAB_DIR = os.path.dirname(os.path.abspath(__file__))
V5_DIR = os.path.join(LAB_DIR, "v5/foyer")
if V5_DIR not in sys.path:
    sys.path.append(V5_DIR)

# [Task 4.2] V5 Foyer Router
from router import FoyerRouter

if __name__ == "__main__":
    import argparse
    import subprocess
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--afk-timeout", type=int, default=300)
    parser.add_argument("--disable-ear", action="store_true", default=False)
    parser.add_argument("--role", default="HUB")
    parser.add_argument("--trigger-task", choices=["recruiter", "lab"])
    args = parser.parse_args()
    
    # [Task 5.2] Spawn Ignition Manager as a sibling process
    ignition_script = os.path.join(LAB_DIR, "v5/ignition/manager.py")
    ignition_proc = subprocess.Popen([sys.executable, ignition_script])
    
    try:
        # [Task 5.2] Execute one-off trigger task if requested
        if args.trigger_task:
            # Check if Foyer is already up
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 8765))
            if result == 0:
                # Foyer is up, use REST
                import requests
                print(f"[BOOT] Foyer active on 8765. Triggering '{args.trigger_task}' via REST...")
                requests.post("http://localhost:8765/trigger_task", json={"task": args.trigger_task}, timeout=5)
                sys.exit(0)
            sock.close()

        # [FEAT-145] "Unity" Dispatcher: Hub Router
        router = FoyerRouter(trigger_task=args.trigger_task)
        router.run()
    finally:
        ignition_proc.terminate()
