import asyncio
import socket
import json
import websockets
import requests
import time

HB_URL = "http://127.0.0.1:9999/heartbeat"
WS_URL = "ws://127.0.0.1:8765"

async def verify_foyer():
    print("[#] Starting Foyer Integrity Probe...")
    
    # 1. Check Attendant State
    try:
        hb = requests.get(HB_URL).json()
        print(f"[*] Attendant Mode: {hb.get('mode')} | Foyer Up: {hb.get('foyer_up')}")
    except Exception as e:
        print(f"[!] Attendant Offline: {e}")
        return

    # 2. Physical Port Probe
    print("[*] Probing Port 8765...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    res = sock.connect_ex(('127.0.0.1', 8765))
    if res == 0:
        print("[+] SUCCESS: Port 8765 is listening.")
    else:
        print(f"[!] FAILURE: Port 8765 is CLOSED (Errno: {res}).")
    sock.close()

    # 3. WebSocket Handshake Test
    if res == 0:
        print("[*] Attempting WebSocket Handshake...")
        try:
            async with websockets.connect(WS_URL, timeout=5) as ws:
                await ws.send(json.dumps({"type": "handshake", "client": "probe"}))
                resp = await ws.recv()
                print(f"[+] Handshake SUCCESS: {resp[:50]}...")
        except Exception as e:
            print(f"[!] Handshake FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(verify_foyer())
