import asyncio
import aiohttp
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from acme_lab import AcmeLab

async def debug_kender():
    lab = AcmeLab()
    print("--- [DEBUG] Verifying KENDER Connection ---")
    await lab.check_brain_health(force=True)
    print(f"Brain Online: {lab.brain_online}")
    if lab.brain_online:
        print("✅ SUCCESS: Lab now sees Windows host.")
    else:
        print("❌ FAILURE: Lab still reports Brain offline.")

if __name__ == "__main__":
    asyncio.run(debug_kender())
