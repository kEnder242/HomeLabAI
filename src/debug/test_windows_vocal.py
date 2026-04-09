import asyncio
import aiohttp
import json
import sys

HUB_URL = "ws://127.0.0.1:8765"

async def test_windows_vocal():
    print("--- [TEST] Windows Vocal Verification ---")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(HUB_URL, timeout=5.0) as ws:
                # 1. Handshake
                await ws.send_str(json.dumps({"type": "handshake", "client": "vocal_prober"}))
                
                # 2. Dispatch Strategic Query
                query = "[ME] ask brain: identify your current host hardware and resident model."
                print(f"    [*] Dispatching: {query}")
                await ws.send_str(json.dumps({"type": "text_input", "content": query}))
                
                # 3. Listen for Brain (Result)
                print("    [*] Awaiting neural response from KENDER...")
                start_t = time.time()
                while time.time() - start_t < 120:
                    msg = await ws.receive_json(timeout=30)
                    m_type = msg.get('type')
                    m_src = msg.get('brain_source', 'None')
                    m_text = msg.get('brain', '')
                    
                    if m_type in ["chat", "crosstalk"] and "Brain" in m_src:
                        print(f"\n[WINDOWS VOCAL]:\n{m_text}")
                        return True
                
                print("  ❌ TIMEOUT: No response from Windows Brain.")
                return False
        except Exception as e:
            print(f"  ❌ Connection Failed: {e}")
            return False

if __name__ == "__main__":
    import time
    asyncio.run(test_windows_vocal())
