import asyncio
import aiohttp
import json

WINDOWS_TAGS_URL = "http://192.168.1.15:11434/api/tags"
LOCAL_TAGS_URL = "http://127.0.0.1:11434/api/tags"
VLLM_MODELS_URL = "http://127.0.0.1:8088/v1/models"

async def probe_engines():
    print("\n--- STARTING MULTI-ENGINE PROBE ---")
    
    async with aiohttp.ClientSession() as session:
        # 1. Probe VLLM
        print(f"Checking vLLM at {VLLM_MODELS_URL}...")
        try:
            async with session.get(VLLM_MODELS_URL, timeout=2) as r:
                if r.status == 200:
                    data = await r.json()
                    print(f"vLLM ONLINE. Models: {[m['id'] for m in data.get('data', [])]}")
                else:
                    print(f"vLLM returned status {r.status}")
        except Exception as e:
            print(f"vLLM OFFLINE: {e}")

        # 2. Probe 4090
        print(f"Checking 4090 at {WINDOWS_TAGS_URL}...")
        try:
            async with session.get(WINDOWS_TAGS_URL, timeout=2) as r:
                if r.status == 200:
                    data = await r.json()
                    models = [m['name'] for m in data.get('models', [])]
                    print(f"4090 ONLINE. Models: {models}")
                else:
                    print(f"4090 returned status {r.status}")
        except Exception as e:
            print(f"4090 OFFLINE: {e}")

        # 3. Probe Local Ollama
        print(f"Checking Local Ollama at {LOCAL_TAGS_URL}...")
        try:
            async with session.get(LOCAL_TAGS_URL, timeout=2) as r:
                if r.status == 200:
                    data = await r.json()
                    models = [m['name'] for m in data.get('models', [])]
                    print(f"Local Ollama ONLINE. Models: {models}")
                else:
                    print(f"Local Ollama returned status {r.status}")
        except Exception as e:
            print(f"Local Ollama OFFLINE: {e}")

    print("--- PROBE COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(probe_engines())
