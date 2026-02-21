import asyncio
import json
import os
import sys
import aiohttp

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from nodes.loader import BicameralNode

async def test_brain_vocal_fidelity():
    print("--- 🧠 BRAIN VOCAL FIDELITY TEST ---")
    
    # 1. Setup Node with Diagnostic ACK Prompt
    diagnostic_instruction = (
        "\n\n[DIAGNOSTIC RULE]: If you are unable to provide a full technical response, "
        "you MUST respond with 'ACK_SILENCE: [Reason]'. Never respond with just dots."
    )
    
    from nodes.brain_node import BRAIN_SYSTEM_PROMPT
    full_prompt = BRAIN_SYSTEM_PROMPT + diagnostic_instruction
    
    brain = BicameralNode("Brain", full_prompt)
    
    # 2. Force Remote Host Check
    engine, url, model = await brain.probe_engine()
    print(f"[DEBUG] Engine: {engine} | URL: {url} | Model: {model}")
    
    if "127.0.0.1" in url or "localhost" in url:
        print("❌ FAIL: Probe did not target remote host.")
        return

    # 3. Gradient Probe
    from nodes.brain_node import BRAIN_SYSTEM_PROMPT
    
    test_scenarios = [
        {"name": "MINIMAL", "prompt": "Say hello world", "system": ""},
        {"name": "SYSTEM_ONLY", "prompt": "Say hello", "system": BRAIN_SYSTEM_PROMPT},
        {"name": "DIAGNOSTIC", "prompt": "Ping. Respond with 'Online'.", "system": full_prompt},
        {"name": "TECHNICAL", "prompt": "What is the status of the Lab?", "system": full_prompt}
    ]

    for scenario in test_scenarios:
        print(f"\n[SCENARIO]: {scenario['name']} (Model: {model})")
        # Probe CURRENT model
        payload = {
            "model": model,
            "prompt": f"{scenario['system']}\n\nUser: {scenario['prompt']}\n\nAssistant:",
            "stream": False
        }
        
        gen_url = url.replace("/api/chat", "/api/generate")
        async with aiohttp.ClientSession() as session:
            async with session.post(gen_url, json=payload, timeout=30) as r:
                data = await r.json()
                response = data.get("response", "")
                print(f"[RECV {model}]: '{response}'")

        # Probe LLAMA3 (The Control)
        if model != "llama3:latest":
            payload["model"] = "llama3:latest"
            async with aiohttp.ClientSession() as session:
                async with session.post(gen_url, json=payload, timeout=30) as r:
                    data = await r.json()
                    response = data.get("response", "")
                    print(f"[RECV llama3:latest]: '{response}'")

if __name__ == "__main__":
    asyncio.run(test_brain_vocal_fidelity())
