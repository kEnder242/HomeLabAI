import asyncio
import json
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.pinky_node import facilitate as pinky_facilitate
from nodes.pinky_node import vram_vibe_check

async def test_native_handshake():
    print("--- 🏁 STARTING NATIVE HANDSHAKE TEST ---")
    
    # We will mock the aiohttp call to verify the logic
    from unittest.mock import patch, AsyncMock
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    # Correctly mock the json() awaitable
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "function": {
                        "name": "ask_brain",
                        "arguments": "{\"task\": \"Calculate Pi\"}"
                    }
                }]
            }
        }]
    }
    
    print("[TEST] Injecting mock vLLM response with tool_calls into Pinky...")
    with patch("aiohttp.ClientSession.post") as mock_post:
        # Make the mock_post return an async context manager that returns mock_resp
        mock_post.return_value.__aenter__.return_value = mock_resp
        
        with patch("nodes.loader.BicameralNode.probe_engine", 
                   return_value=("VLLM", "http://localhost:8088/v1/chat/completions", "mistral-7b-awq")):
            res = await pinky_facilitate("What is Pi?", "context")
            print(f"[RECV] Response: {res}")
            
            data = json.loads(res)
            if data.get("tool") == "ask_brain":
                print("[PASS] Native tool call correctly unwrapped to internal JSON.")
            else:
                print("[FAIL] Native tool call not correctly unwrapped.")
                sys.exit(1)

    print("[TEST] Verifying NVML bindings in Pinky Node...")
    res = await vram_vibe_check()
    print(f"[RECV] {res}")
    if "VRAM Status" in res:
        print("[PASS] NVML bindings active and reporting.")
    else:
        print("[FAIL] NVML bindings failed.")
        sys.exit(1)

    print("--- ✅ ALL NATIVE BASELINE TESTS PASSED ---")

if __name__ == "__main__":
    asyncio.run(test_native_handshake())
