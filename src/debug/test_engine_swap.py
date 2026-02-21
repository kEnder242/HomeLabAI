import asyncio
import json
import os
import aiohttp
import time

ATTENDANT_URL = "http://localhost:9999"
VRAM_CONFIG_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/vram_characterization.json")

async def test_engine_swap_protocol():
    print("--- 🏎️ Testing Engine Swap Protocol ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab in vLLM mode
        print("[TEST] Ensuring Lab is running in vLLM mode...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "vLLM"})
        print("[TEST] Waiting for READY state (up to 120s)...")
        await session.get(f"{ATTENDANT_URL}/wait_ready?timeout=120")
        
        # 2. Get current VRAM
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            current_vram = info.used // 1024 // 1024
            pynvml.nvmlShutdown()
            print(f"[TEST] Current VRAM: {current_vram} MiB")
        except Exception:
            current_vram = 2000

        # 3. Artificially lower the WARNING threshold
        print("[TEST] Artificially lowering WARNING threshold...")
        with open(VRAM_CONFIG_PATH, "r") as f:
            config = json.load(f)
        
        original_warning = config["safe_tiers"]["warning"]
        # Set warning well below current usage to guarantee trigger
        config["safe_tiers"]["warning"] = 500
        
        with open(VRAM_CONFIG_PATH, "w") as f:
            json.dump(config, f)

        try:
            # 4. Trigger refresh
            print("[TEST] Triggering Attendant Refresh...")
            await session.post(f"{ATTENDANT_URL}/refresh")
            
            # 5. Wait for watchdog to bite (loop is 2s)
            print("[TEST] Waiting for Engine Swap (30s)...")
            await asyncio.sleep(30)
            
            # 6. Verify Lab is running in OLLAMA mode
            print("[TEST] Waiting for OLLAMA mode in status.json vitals...")
            success = False
            for _ in range(30): # 30 retries (shorter interval)
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    vitals = await resp.json()
                
                curr_mode = vitals.get('lab_mode')
                print(f"[RETRY] Lab Mode: {curr_mode}")
                if curr_mode == "OLLAMA":
                    print("[PASS] Engine Swap Protocol triggered successfully (Engine swapped to OLLAMA).")
                    success = True
                    break
                await asyncio.sleep(1)

            if not success:
                print("[FAIL] System did not perform engine swap or timed out.")
                exit(1)

        finally:
            # Restore config
            print("[TEST] Restoring original config...")
            config["safe_tiers"]["warning"] = original_warning
            with open(VRAM_CONFIG_PATH, "w") as f:
                json.dump(config, f)
            await session.post(f"{ATTENDANT_URL}/refresh")

if __name__ == "__main__":
    asyncio.run(test_engine_swap_protocol())
