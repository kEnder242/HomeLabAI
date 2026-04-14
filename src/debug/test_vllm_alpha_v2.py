import asyncio
import aiohttp
import time
import sys

async def test_connectivity():
    """[TIER 1] Pure connectivity check for the vLLM OpenAI-compatible endpoint."""
    url = "http://127.0.0.1:8088/v1/models"
    timeout = 180 # 180s cold-start JIT delay for Turing
    start_t = time.time()
    
    print(f"🚀 Initializing VLLM Alpha connectivity check: {url}")
    print(f"⏳ Timeout window: {timeout}s (Accounting for JIT compilation)")
    
    while time.time() - start_t < timeout:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=2.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        print(f"✅ SUCCESS: vLLM replied in {time.time() - start_t:.1f}s")
                        print(f"📦 Models: {[m['id'] for m in data.get('data', [])]}")
                        return True
        except Exception:
            pass
        
        await asyncio.sleep(5)
        print(f"  ... waiting for engine ({int(time.time() - start_t)}s elapsed)")
        
    print(f"❌ FAILED: vLLM did not respond within {timeout}s")
    return False

if __name__ == "__main__":
    if asyncio.run(test_connectivity()):
        sys.exit(0)
    else:
        sys.exit(1)
