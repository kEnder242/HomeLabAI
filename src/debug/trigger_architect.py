import asyncio
import os
import sys

# Ensure nodes can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.architect_node import build_semantic_map

async def run():
    print("[DEBUG] Standalone Architect Trigger: Deepening Semantic Map...")
    res = await build_semantic_map()
    print(f"[DEBUG] Result: {res}")

if __name__ == "__main__":
    asyncio.run(run())
