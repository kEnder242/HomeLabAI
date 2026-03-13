import asyncio
import aiohttp
import time
import os
import sys

# --- Path Self-Awareness ---
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_LAB_ROOT = os.path.abspath(os.path.join(_SELF_DIR, "..", ".."))
sys.path.insert(0, os.path.join(_LAB_ROOT, "src"))

# Configuration from Environment or Defaults
ATTENDANT_URL = os.environ.get("ATTENDANT_URL", "http://localhost:9999")
VLLM_URL = "http://localhost:8088/v1/chat/completions" # Direct to vLLM
SERVED_NAME = "unified-base"

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
    print(f"\n[APOLLO] Initiating Token Burn ({SERVED_NAME})...")
    payload = {
        "model": SERVED_NAME,
        "messages": [
            {
                "role": "user",
                "content": "Explain the concept of VRAM headroom in one paragraph."
            }
        ],
        "max_tokens": 100
    }
    try:
        async with session.post(VLLM_URL, json=payload) as resp:
            data = await resp.json()
            if "choices" in data:
                print("[APOLLO] Token Burn Complete.")
            else:
                print(f"[APOLLO] Token Burn Failed (No Choice): {data}")
    except Exception as e:
        print(f"[APOLLO] Token Burn Failed: {e}")


async def run_apollo_live(model_name="/speedy/models/qwen-2.5-1.5b-awq", disable_ear=True):
    print(f"--- 🚀 Apollo 11: V3 Active Profiling ({model_name}) ---")

    # 1. Hardware Detection
    used_base, total_cap = get_gpu_info()
    if total_cap == 0:
        print("[ERROR] No NVIDIA GPU detected. Aborting.")
        return

    print(f"[APOLLO] Detected GPU Capacity: {total_cap} MiB")
    print(f"[APOLLO] Baseline VRAM: {used_base} MiB")

    # 2. Check current status and ignite via V3 schema
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                status = await resp.json()
            
            if status.get("full_lab_ready") and status.get("lab_mode") == "VLLM":
                print("[APOLLO] Lab already READY in vLLM mode. Proceeding.")
            else:
                print("[APOLLO] Signaling V3 Master for ignition...")
                # V3 Start Schema: engine, model, disable_ear
                payload = {"engine": "VLLM", "model": model_name, "disable_ear": disable_ear}
                async with session.post(f"{ATTENDANT_URL}/start", json=payload) as resp:
                    res = await resp.json()
                    print(f"[APOLLO] Master Signal: {res.get('message')}")
        except Exception as e:
            print(f"[ERROR] Could not connect to Attendant: {e}")
            return

        start_time = time.time()
        max_vram = used_base
        burn_triggered = False

        # 300s timeout for load (vLLM can be slow) + burn
        while time.time() - start_time < 300:
            current, _ = get_gpu_info()
            if current > max_vram:
                max_vram = current

            try:
                async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                    status = await resp.json()

                if status.get("full_lab_ready") and not burn_triggered:
                    print("\n[APOLLO] Lab is READY. Starting stress phase.")
                    asyncio.create_task(token_burn(session))
                    burn_triggered = True

                if burn_triggered and time.time() - start_time > 200:
                    break # Captured peak

                if status.get("last_error"):
                    print(f"\n[APOLLO] FAILURE: {status['last_error']}")
                    break
            except Exception:
                pass

            print(
                f"\r[APOLLO] Current VRAM: {current:>5} MiB | Peak: {max_vram:>5} MiB",
                end="", flush=True
            )
            await asyncio.sleep(1)

        print(f"\n[APOLLO] Final Peak (Active): {max_vram} MiB")
        pct = (max_vram / total_cap) * 100
        print(f"[APOLLO] Budget: {max_vram} / {total_cap} MiB ({pct:.1f}%)")

        if max_vram > total_cap * 0.95:
            print("[CRITICAL] REDLINE. Active silicon pressure detected.")
        else:
            print("[NOMINAL] Active silicon headroom verified.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/speedy/models/qwen-2.5-1.5b-awq")
    parser.add_argument("--enable-ear", action="store_true", default=False)
    args = parser.parse_args()
    
    asyncio.run(run_apollo_live(model_name=args.model, disable_ear=not args.enable_ear))
