import asyncio
import aiohttp
import socket
import sys

# --- Configuration ---
COMPONENTS = {
    "Lab Attendant": {"type": "http", "url": "http://127.0.0.1:9999/heartbeat"},
    "vLLM Engine":   {"type": "http", "url": "http://127.0.0.1:8088/v1/models"},
    "Lab Server":    {"type": "socket", "host": "127.0.0.1", "port": 8765},
    "Prometheus":    {"type": "http", "url": "http://127.0.0.1:9090/-/healthy"},
    "Grafana":       {"type": "http", "url": "http://127.0.0.1:3000/api/health"},
    "Node Exporter": {"type": "http", "url": "http://127.0.0.1:9100/metrics"},
    "RAPL Sim":      {"type": "http", "url": "http://127.0.0.1:8000/metrics"},
    "DCGM Exporter": {"type": "http", "url": "http://127.0.0.1:9400/metrics"},
}

async def check_http(name, url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as r:
                if r.status < 400:
                    return True, f"HTTP {r.status}"
                return False, f"HTTP {r.status}"
    except Exception as e:
        return False, "Unreachable"

async def check_socket(name, host, port):
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2)
        writer.close()
        await writer.wait_closed()
        return True, "Open"
    except Exception as e:
        return False, "Closed"

async def run_audit():
    print("\n--- 🏥 Acme Lab Full-Stack Liveliness Audit ---")
    all_pass = True
    
    for name, cfg in COMPONENTS.items():
        if cfg["type"] == "http":
            success, msg = await check_http(name, cfg["url"])
        else:
            success, msg = await check_socket(name, cfg["host"], cfg["port"])
            
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {name:15} : {msg}")
        if not success:
            all_pass = False
            
    if all_pass:
        print("\n✨ ALL SYSTEMS NOMINAL\n")
    else:
        print("\n⚠️  DEGRADED STATE DETECTED\n")
    return all_pass

if __name__ == "__main__":
    success = asyncio.run(run_audit())
    sys.exit(0 if success else 1)
