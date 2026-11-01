import asyncio
import json
import sys
import urllib.request
import aiohttp

WS_URL = "ws://127.0.0.1:8765/hub"
STATUS_URL = "http://127.0.0.1:8765/status?timeout=2"

async def test_live_operational_query():
    print("[1] Getting session token from /status...")
    with urllib.request.urlopen(STATUS_URL, timeout=5) as resp:
        status_data = json.loads(resp.read().decode("utf-8"))
        session_token = status_data.get("session_token", "")
        print(f"    Session token: {session_token} | Daemon state: {status_data.get('state')}")

    print("[2] Connecting to live WebSocket on port 8765 with authenticated handshake...")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL, timeout=20) as ws:
            await ws.send_json({
                "type": "handshake",
                "version": "5.0.0-foyer",
                "lab_key": session_token,
            })
            print("    Authenticated handshake sent.")

            # Send operational telemetry query
            query = "[ME] What are our live GPU thermals right now?"
            await ws.send_json({"type": "text_input", "content": query})
            print(f"    Dispatched live query: '{query}'")

            packets = []
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    packets.append(data)
                    src = data.get("source") or data.get("brain_source", "")
                    tok = data.get("brain") or data.get("token") or data.get("text", "")
                    if tok and len(tok.strip()) > 0:
                        print(f"    [{src or 'WS'}]: {tok[:80]}")
                    if data.get("final") is True:
                        print("    Received final stream packet.")
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

    print(f"[3] Total live packets received: {len(packets)}")
    return len(packets) > 0

if __name__ == "__main__":
    success = asyncio.run(test_live_operational_query())
    sys.exit(0 if success else 1)
