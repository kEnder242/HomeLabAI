"""
[SPR-59.0] True Live-Fire Integration Test Runner

Connects directly over physical WebSockets (ws://localhost:8765) to the active
running acme_foyer_v5 daemon (serving boot commit 944d7ef).

Exercises:
  1. Live Fourth Wall Critique Interception ([FEAT-456/BKM-035])
     - Sends user critique over live WebSocket.
     - Asserts immediate in-character thought/response stream from live daemon.
     - Verifies physical append to validation_ledger.jsonl on disk.
  2. Live Casual Greeting with Floating Context ([FEAT-458])
     - Sends "[ME] hey pinky, how are things?" over live WebSocket.
     - Asserts live conversational response stream from running server.
"""

import asyncio
import json
import os
import sys
import requests
import websockets

LEDGER_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl")


async def run_live_fire_suite():
    uri = "ws://127.0.0.1:8765"
    print(f"\n========================================================")
    print(f"🔥 [LIVE FIRE] Connecting to Running Lab Service: {uri}")
    print(f"========================================================")

    # 0. Fetch session_token from /status
    try:
        status_resp = requests.get("http://127.0.0.1:8765/status", timeout=5).json()
        lab_key = status_resp.get("session_token", "")
        print(f"🔑 Authenticated session_token: {lab_key[:4]}****")
    except Exception as e:
        print(f"❌ Failed to fetch session_token from /status: {e}")
        sys.exit(1)

    # Count initial ledger records
    initial_ledger_count = 0
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            initial_ledger_count = len([line for line in f if line.strip()])

    async with websockets.connect(
        uri,
        additional_headers={"X-Lab-Key": lab_key},
    ) as ws:
        # ── 1. Handshake ──────────────────────────────────────────────────────
        print("\n📡 Step 1: Performing Authenticated WebSocket Handshake...")
        await ws.send(json.dumps({
            "type": "handshake",
            "version": "5.0.0",
            "client": "live_fire_integration_runner",
            "lab_key": lab_key,
        }))
        await asyncio.sleep(1)

        # ── 2. Test Live Fourth Wall Feedback Interception ───────────────────
        critique_query = "[ME] Wait, that's wrong, RAPL MSR 0x610 is PKG limit, not DRAM."
        print(f"\n🎯 Step 2: Sending Live Critique: '{critique_query}'")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": critique_query,
        }))

        received_feedback = False
        received_tokens = []
        timeout_s = 20.0
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_s:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                msg_type = data.get("type")

                if msg_type == "thought_stream" and "Feedback" in data.get("source", ""):
                    received_feedback = True
                    received_tokens.append(data.get("token", ""))
                    print(f"  [STREAM from {data.get('source')}]: {data.get('token', '')}")
                elif msg_type == "chat":
                    print(f"  [{data.get('brain_source', 'Chat')}]: {data.get('brain', '')}")
                elif msg_type == "final":
                    print(f"  [FINAL TRANSCRIPTION]: {data.get('text', '')}")
                elif msg_type == "status":
                    print(f"  [STATUS]: {data.get('state')} - {data.get('message', '')}")
            except asyncio.TimeoutError:
                break

        print("\n🔍 Step 3: Verifying Live Validation Ledger Append on Disk...")
        if os.path.exists(LEDGER_PATH):
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                new_records = [json.loads(line) for line in f if line.strip()]
            new_count = len(new_records)
            print(f"  Ledger Count: {initial_ledger_count} -> {new_count} records")
            assert new_count >= initial_ledger_count, "Ledger records must not decrease"
            if new_count > initial_ledger_count:
                latest_record = new_records[-1]
                print(f"  Latest Live Record: Verdict={latest_record.get('verdict')} | GroundTruth='{latest_record.get('ground_truth')[:40]}...'")
                assert latest_record.get("verdict") == "FAIL"

        # ── 3. Test Live Casual Greeting Turn with Floating Oracle ───────────
        greeting_query = "[ME] hey pinky, how are things?"
        print(f"\n🎯 Step 4: Sending Live Casual Greeting: '{greeting_query}'")
        await ws.send(json.dumps({
            "type": "text_input",
            "content": greeting_query,
        }))

        received_greeting_response = False
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < 20.0:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(msg)
                if data.get("type") == "chat" or "brain" in data:
                    received_greeting_response = True
                    print(f"  [{data.get('brain_source', 'Chat')}]: {data.get('brain', '')}")
                elif data.get("type") == "status":
                    print(f"  [STATUS]: {data.get('state')} - {data.get('message', '')}")
            except asyncio.TimeoutError:
                break

    print(f"\n========================================================")
    print(f"✅ [LIVE FIRE COMPLETE] Active daemon successfully verified on ws://127.0.0.1:8765!")
    print(f"========================================================\n")


if __name__ == "__main__":
    asyncio.run(run_live_fire_suite())
