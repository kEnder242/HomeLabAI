import asyncio
import subprocess
import aiohttp
import time
import os
import json

# Configuration from Environment or Defaults
ATTENDANT_URL = os.environ.get("ATTENDANT_URL", "http://localhost:9999")
VLLM_URL = "http://localhost:8088/v1/chat/completions"
MODEL_PATH = "/home/jallred/AcmeLab/models/mistral-7b-awq"


def get_gpu_info():
    """Returns (used, total) MiB."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        used = info.used // 1024 // 1024
        total = info.total // 1024 // 1024
        pynvml.nvmlShutdown()
        return used, total
    except Exception:
        return 0, 0


async def token_burn(session):
    """Fires a request to vLLM to allocate KV cache."""
    print("\n[APOLLO] Initiating Token Burn (KV Cache Allocation)...")
    payload = {
        "model": MODEL_PATH,
        "messages": [
            {"role": "user", "content": "Explain the concept of VRAM headroom in one paragraph."}
        ],
        "max_tokens": 100
    }
    try:
        async with session.post(VLLM_URL, json=payload) as resp:
            await resp.json()
            print("[APOLLO] Token Burn Complete.")
    except Exception as e:
        print(f"[APOLLO] Token Burn Failed: {e}")


async def run_apollo_live():
    print("--- 🚀 Apollo 11: Real-Time Active Profiling (Mistral-7B) ---")

    # 1. Hardware Detection
    used_base, total_cap = get_gpu_info()
    if total_cap == 0:
        print("[ERROR] No NVIDIA GPU detected. Aborting.")
        return

    print(f"[APOLLO] Detected GPU Capacity: {total_cap} MiB")
    print(f"[APOLLO] Baseline VRAM: {used_base} MiB")

    # 2. Trigger Start via Attendant
    async with aiohttp.ClientSession() as session:
        print("[APOLLO] Launching Full Stack (vLLM + Ears)...")
        try:
            await session.post(
                f"{ATTENDANT_URL}/start",
                json={"engine": "vLLM", "disable_ear": False}
            )
        except Exception as e:
            print(f"[ERROR] Could not connect to Attendant: {e}")
            return

        start_time = time.time()
        max_vram = used_base
        burn_triggered = False

        # 180s timeout for load + burn
        while time.time() - start_time < 180:
            current, _ = get_gpu_info()
            if current > max_vram:
                max_vram = current

            try:
                resp = await session.get(f"{ATTENDANT_URL}/status?timeout=1")
                status = await resp.json()

                if status.get("full_lab_ready") and not burn_triggered:
                    print("\n[APOLLO] Lab is READY. Starting stress phase.")
                    # Run burn in background to keep monitoring peak
                    asyncio.create_task(token_burn(session))
                    burn_triggered = True

                if burn_triggered and time.time() - start_time > 150:
                    # Give it time to finish generation
                    break

                if status.get("last_error"):
                    print(f"\n[APOLLO] FAILURE DETECTED: {status['last_error']}")
                    break
            except Exception:
                pass

            print(
                f"\r[APOLLO] Current VRAM: {current:>5} MiB | Peak: {max_vram:>5} MiB",
                end="", flush=True
            )
            await asyncio.sleep(1)

        print(f"\n[APOLLO] Final Peak (Active): {max_vram} MiB")
        print(f"[APOLLO] Budget: {max_vram} / {total_cap} MiB ({(max_vram/total_cap)*100:.1f}%)")

        if max_vram > total_cap * 0.95:
            print("[CRITICAL] REDLINE. Active inference is dangerously close to OOM.")
        else:
            print("[NOMINAL] Active silicon headroom verified.")

if __name__ == "__main__":
    asyncio.run(run_apollo_live())
