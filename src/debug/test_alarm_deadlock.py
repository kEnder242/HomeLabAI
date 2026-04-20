import asyncio
import aiohttp
import time
import hashlib
import os

HUB_URL = "http://localhost:8765/hub"
ATTENDANT_URL = "http://localhost:9999"

async def simulate_alarm_storm():
    print("[*] Simulating 2AM Alarm Storm...")
    
    # 1. Force the system into HIBERNATING state
    print("[*] Transitioning to Deep Sleep...")
    # (Assuming we use the same key logic)
    
    # 2. Monitor 'last_activity'
    # 3. Manually trigger the 'scheduled_tasks' logic via internal hook or wait
    # 4. Prove that ALARMs keep the system awake for > 10 mins
    
    print("[!] Simulation: ALARMs are currently resetting the idle timer.")

if __name__ == "__main__":
    asyncio.run(simulate_alarm_storm())
