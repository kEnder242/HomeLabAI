import asyncio
import aiohttp
import time

BRAIN_URL = "http://192.168.1.26:11434/api/generate"
MODEL = "llama3.1:8b"

async def measure_think(query, system_override=None):
    print(f"\n--- [TEST] Query: '{query}' ---")
    
    prompt = query
    if system_override:
        prompt = f"System: {system_override}\n\nUser: {query}\n\nAssistant:"
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 100,
            "temperature": 0.1
        }
    }

    async with aiohttp.ClientSession() as session:
        print("[PRIME] Sending single-token probe...")
        await session.post(BRAIN_URL, json={
            "model": MODEL, "prompt": "ping", "stream": False, "options": {"num_predict": 1}
        })
        
        print("[THINK] Sending query...")
        start_t = time.time()
        async with session.post(BRAIN_URL, json=payload) as r:
            end_t = time.time()
            data = await r.json()
            
            total_duration = data.get("total_duration", 0) / 1e9
            load_duration = data.get("load_duration", 0) / 1e9
            eval_count = data.get("eval_count", 0)
            response = data.get("response", "").strip()
            
            print(f"Response: {response}")
            print(f"Wall Clock Time: {end_t - start_t:.2f}s")
            print(f"Ollama Total Duration: {total_duration:.2f}s")
            print(f"Ollama Load Duration: {load_duration:.2f}s")
            print(f"Actual Generation Time: {total_duration - load_duration:.2f}s")
            print(f"Token Count: {eval_count}")
            
            return {
                "wall_time": end_t - start_t,
                "gen_time": total_duration - load_duration,
                "tokens": eval_count,
                "response": response
            }

async def run_suite():
    print("=== BASELINE: REGULAR BRAIN ===")
    await measure_think("Brain, are you there?")

    print("\n=== SHALLOW THINK: LACONIC OVERRIDE ===")
    shallow_prompt = "You are a fast, laconic analytical assistant. Reply in < 10 words. No chatter."
    await measure_think("Brain, are you there?", system_override=shallow_prompt)

if __name__ == "__main__":
    asyncio.run(run_suite())
