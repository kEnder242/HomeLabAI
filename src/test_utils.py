import json
import subprocess
import os
import aiohttp
import asyncio
import websockets

ATTENDANT_URL = "http://localhost:9999"
LAB_WS_URL = "ws://localhost:8765"
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_current_commit():
    """Gets the short commit hash of the current disk source."""
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], 
                                    cwd=LAB_DIR, text=True).strip()
    except Exception:
        return "unknown"

async def ensure_smart_lab(disable_ear=True):
    """
    [FEAT-125] Smart-Reuse Logic:
    1. Check if Lab is already running via Heartbeat.
    2. If up -> Clear memory via Neuralyzer.
    3. If down -> Hard Reset and wait for new boot.
    """
    
    # 1. Check if Lab is already running via Attendant
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{ATTENDANT_URL}/heartbeat") as resp:
                status = await resp.json()
                if status.get("lab_server_running") and status.get("full_lab_ready"):
                    print("✨ [SMART-REUSE] Active Lab found. Wiping context...")
                    try:
                        async with websockets.connect(LAB_WS_URL) as ws:
                            await ws.send(json.dumps({"type": "handshake", "version": "3.8.0"}))
                            await asyncio.sleep(1)
                            await ws.send(json.dumps({"type": "text_input", "content": "Neuralyzer"}))
                            await asyncio.sleep(1)
                            return True
                    except Exception as e:
                        print(f"⚠️ Could not wipe context: {e}")
                        # Continue to hard reset if WS fails
        except Exception:
            pass

    # 2. Down: Perform Hard Start
    print("🚀 [BOOT] Starting fresh Lab instance...")
    async with aiohttp.ClientSession() as session:
        # Atomic purge
        await session.post(f"{ATTENDANT_URL}/hard_reset")
        await asyncio.sleep(2) 
        async with session.post(f"{ATTENDANT_URL}/start", json={"mode": "SERVICE_UNATTENDED", "disable_ear": disable_ear}) as resp:
            # Wait for ready
            for _ in range(60):
                try:
                    async with session.get(f"{ATTENDANT_URL}/heartbeat") as h_resp:
                        h_status = await h_resp.json()
                        if h_status.get("full_lab_ready"):
                            print("✅ Fresh Lab READY.")
                            return True
                except Exception:
                    pass
                await asyncio.sleep(1)
    
    return False
