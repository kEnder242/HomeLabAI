import asyncio
import aiohttp

VLLM_URL = "http://127.0.0.1:8088/v1/chat/completions"
MODEL = "llama-3.2-3b-awq"

async def repro():
    print("--- 🧪 vLLM Fix Verify: Unified User Pattern ---")

    # Unified structure as implemented in pinky_node.py
    unified_content = (
        "[SYSTEM]: You are Pinky. Narf!\n\n"
        "MEMORY: None\n\n"
        "QUERY: Hello!\n\n"
        "DECISION (JSON):"
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": unified_content}],
        "max_tokens": 100,
        "temperature": 0.2
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(VLLM_URL, json=payload, timeout=10) as resp:
                data = await resp.json()
                print(f"Status: {resp.status}")
                if resp.status == 200:
                    print("SUCCESS! vLLM accepted the unified user message.")
                    print(f"Response: {data['choices'][0]['message']['content'][:50]}...")
                else:
                    print(f"DATA: {data}")
        except Exception as e:
            print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(repro())
