import asyncio
import os
import sys

# V5 Transition Shim
# [Task 2.1] The Clean Cut

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
    
    # [BUGFIX] Spawn MCP Server
    mcp_script = os.path.join(LAB_DIR, "acme_lab_mcp.py")
    mcp_proc = subprocess.Popen([sys.executable, mcp_script], cwd=LAB_DIR)
    
    try:
        router = FoyerRouter()
        router.run()
    finally:
        ignition_proc.terminate()
        mcp_proc.terminate()
