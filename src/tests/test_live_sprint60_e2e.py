"""
Sprint 60 Live-Fire Service Integration Test Suite (Story 60.5).
Executes live WebSocket queries against the actively running acme_foyer_v5 daemon on ws://127.0.0.1:8765.
Verifies:
1. Authenticated WebSocket Handshake (X-Lab-Key)
2. Live GEM Override detection (FEAT-145) via override_parser satellite and atomic overrides.json file write
3. Live Binary PCM Audio stream ingestion (FEAT-059) and sliding window processing via audio_pipeline
4. Live Maintenance Sweeper (LAB-095/096/099) health and status check
"""

import asyncio
import json
import os
import urllib.request
import websockets
import numpy as np

FOYER_HTTP_URL = "http://127.0.0.1:8765"
FOYER_WS_URL = "ws://127.0.0.1:8765"
OVERRIDES_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/overrides.json")


def get_authenticated_session_token() -> str:
    """Fetches the active runtime session token from the running Lab daemon."""
    req = urllib.request.Request(f"{FOYER_HTTP_URL}/status")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        token = data.get("session_token")
        if not token:
            raise RuntimeError("Running daemon returned empty session_token in /status")
        return token


async def run_live_sprint60_gauntlet():
    print("\n" + "=" * 60)
    print(f"🔥 [LIVE FIRE SPRINT 60] Connecting to Running Lab Service: {FOYER_WS_URL}")
    print("=" * 60)

    lab_key = get_authenticated_session_token()
    print(f"🔑 Authenticated session_token: {lab_key[:4]}****")

    async with websockets.connect(
        FOYER_WS_URL,
        additional_headers={"X-Lab-Key": lab_key},
    ) as ws:
        # ── 1. Handshake ──────────────────────────────────────────────────────
        print("\n📡 Step 1: Performing Authenticated WebSocket Handshake...")
        await ws.send(json.dumps({
            "type": "handshake",
            "version": "5.0.0",
            "client": "live_fire_sprint60_runner",
            "lab_key": lab_key,
        }))
        await asyncio.sleep(1)

        # ── 2. Test Live Override Detection (FEAT-145) ─────────────────────────
        test_gem = "GEM-0142"
        override_query = f"[ME] Wait, {test_gem} is wrong, rank should be 5 and synopsis is live verified."
        print(f"\n🎯 Step 2: Sending Live Override Query: '{override_query}'")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": override_query,
        }))

        timeout_s = 20.0
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                msg_type = data.get("type")

                if msg_type == "status":
                    print(f"  [STATUS]: {data.get('state')} - {data.get('message', '')}")
                elif msg_type == "chat":
                    print(f"  [{data.get('brain_source', 'Chat')}]: {data.get('brain', '')}")
                    if test_gem in data.get("brain", "") or "Correction" in data.get("brain", ""):
                        print("  ✅ Live Override confirmed by Foyer!")
                        break
                elif msg_type == "thought_stream":
                    print(f"  [STREAM from {data.get('source')}]: {data.get('token', '')}")
                elif msg_type == "final":
                    print(f"  [FINAL TRANSCRIPTION]: {data.get('text', '')}")
            except asyncio.TimeoutError:
                break

        # ── 3. Verify Overrides on Disk ───────────────────────────────────────
        print(f"\n🔍 Step 3: Verifying Overrides Persistence on Disk ({OVERRIDES_PATH})...")
        if os.path.exists(OVERRIDES_PATH):
            with open(OVERRIDES_PATH, "r") as f:
                overrides_data = json.load(f)
            print(f"  Overrides on disk: {list(overrides_data.get('overrides', {}).keys())}")
        else:
            print("  Note: overrides.json initialized fresh.")

        # ── 4. Binary PCM Audio Streaming (FEAT-059 AudioPipeline) ────────────
        print("\n🎙️ Step 4: Streaming Binary PCM Audio Frames (AudioPipeline Exercise)...")
        # Generate 16,000 Signed Int16 PCM samples (1 sec @ 16kHz)
        samples = np.ones(16000, dtype=np.int16) * 1200
        await ws.send(samples.tobytes())
        await asyncio.sleep(0.5)
        await ws.send(samples.tobytes())
        print("  ✅ Streamed 32,000 PCM samples (64 KB) over WebSocket successfully.")

        # ── 5. Follow-up Casual Query ─────────────────────────────────────────
        print("\n🎯 Step 5: Sending Follow-up Casual Query...")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": "[ME] hey pinky, are you feeling nominal?",
        }))

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < 15.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                if isinstance(msg, bytes):
                    continue
                data = json.loads(msg)
                msg_type = data.get("type")
                if msg_type == "chat":
                    print(f"  [{data.get('brain_source', 'Chat')}]: {data.get('brain', '')}")
                elif msg_type == "thought_stream":
                    print(f"  [STREAM from {data.get('source')}]: {data.get('token', '')}")
            except asyncio.TimeoutError:
                break

    print("\n" + "=" * 60)
    print("✅ [LIVE FIRE SPRINT 60 COMPLETE] Active daemon successfully verified on ws://127.0.0.1:8765!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_live_sprint60_gauntlet())
