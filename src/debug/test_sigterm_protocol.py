import asyncio
import json
import os
import aiohttp
import time

ATTENDANT_URL = "http://localhost:9999"
VRAM_CONFIG_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/vram_characterization.json")

async def test_sigterm_protocol():
    print("--- 🛡️ Testing SIGTERM Protocol (VRAM Pre-emption) ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Ensure Lab is running
        print("[TEST] Ensuring Lab is running...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "OLLAMA"}) # Faster start
        await session.get(f"{ATTENDANT_URL}/wait_ready?timeout=60")
        
        # 2. Get current VRAM usage
        async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
            vitals = await resp.json()
            print(f"[TEST] Current VRAM: {vitals.get('vram')}")

        # 3. Maliciously lower the threshold in config
        print("[TEST] Artificially lowering threshold...")
        with open(VRAM_CONFIG_PATH, "r") as f:
            config = json.load(f)
        
        original_critical = config["safe_tiers"]["critical"]
        # Set critical to 1000 MiB (well below current usage)
        config["safe_tiers"]["critical"] = 1000
        
        with open(VRAM_CONFIG_PATH, "w") as f:
            json.dump(config, f)

        try:
            # 4. Trigger refresh
            print("[TEST] Triggering Attendant Refresh...")
            await session.post(f"{ATTENDANT_URL}/refresh")
            
            # 5. Wait for watchdog to bite (loop is 10s)
            print("[TEST] Waiting for Watchdog (15s)...")
            await asyncio.sleep(15)
            
            # 6. Verify Lab is STOPPED
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                final_vitals = await resp.json()
                print(f"[TEST] Lab Server Running: {final_vitals.get('lab_server_running')}")
                
                if not final_vitals.get('lab_server_running'):
                    print("[PASS] SIGTERM Protocol triggered pre-emption successfully.")
                else:
                    print("[FAIL] Lab server still running despite VRAM pressure.")
                    exit(1)

        finally:
            # Restore config
            print("[TEST] Restoring original config...")
            config["safe_tiers"]["critical"] = original_critical
            with open(VRAM_CONFIG_PATH, "w") as f:
                json.dump(config, f)
            await session.post(f"{ATTENDANT_URL}/refresh")

if __name__ == "__main__":
    asyncio.run(test_sigterm_protocol())
