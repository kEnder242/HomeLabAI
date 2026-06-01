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
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED")
    parser.add_argument("--role", default="HUB")
    args = parser.parse_args()
    
    router = FoyerRouter()
    router.run()
