import asyncio
import json
import os
import aiohttp
import time

ATTENDANT_URL = "http://localhost:9999"
VRAM_CONFIG_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/vram_characterization.json")

async def test_downshift_protocol():
    print("--- 🪜 Testing Tier 3 Downshift Protocol ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Start Lab in OLLAMA mode (Gemma default)
        print("[TEST] Ensuring Lab is running in OLLAMA (Gemma) mode...")
        await session.post(f"{ATTENDANT_URL}/start", json={"engine": "OLLAMA"})
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
            current_vram = 3000

        # 3. Artificially lower the DOWNSHIFT threshold
        print("[TEST] Artificially lowering DOWNSHIFT threshold...")
        with open(VRAM_CONFIG_PATH, "r") as f:
            config = json.load(f)
        
        original_downshift = config["safe_tiers"]["downshift"]
        # Set downshift well below current usage
        config["safe_tiers"]["downshift"] = current_vram - 100
        
        with open(VRAM_CONFIG_PATH, "w") as f:
            json.dump(config, f)

        try:
            # 4. Trigger refresh
            print("[TEST] Triggering Attendant Refresh...")
            await session.post(f"{ATTENDANT_URL}/refresh")
            
            # 5. Wait for watchdog to bite (loop is 10s)
            print("[TEST] Waiting for Downshift (20s)...")
            await asyncio.sleep(20)
            
            # 6. Verify Lab is running in OLLAMA mode with Llama 1B
            print("[TEST] Waiting for SMALL tier model in status.json vitals...")
            # Get expected model name from config
            with open(VRAM_CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            expected_model = cfg["model_map"]["SMALL"]["ollama"]
            print(f"[TEST] Expected: {expected_model}")

            success = False
            for _ in range(15): # 15 retries
                # Check status.json vitals
                s_json = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/data/status.json"
                try:
                    with open(s_json, "r") as f:
                        status_data = json.load(f)
                    current_model = status_data.get("vitals", {}).get("model")
                    print(f"[RETRY] Current Model: {current_model}")
                    if current_model == expected_model:
                        print(f"[PASS] Downshift Protocol triggered successfully (Model swapped to {expected_model}).")
                        success = True
                        break
                except: pass
                await asyncio.sleep(2)

            if not success:
                print("[FAIL] System did not downshift model or model vital timed out.")
                exit(1)

        finally:
            # Restore config
            print("[TEST] Restoring original config...")
            config["safe_tiers"]["downshift"] = original_downshift
            with open(VRAM_CONFIG_PATH, "w") as f:
                json.dump(config, f)
            await session.post(f"{ATTENDANT_URL}/refresh")

if __name__ == "__main__":
    asyncio.run(test_downshift_protocol())
