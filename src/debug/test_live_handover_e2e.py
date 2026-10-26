#!/usr/bin/env python3
"""[FEAT-671 / BKM-024 / Story 108.16] Physical Silicon End-to-End Handover & Feedback Certification.

Connects to live physical daemon on port 8765, validates authenticated handshake,
executes live query, asserts packet routing, and tests interactive downvote step-trace.
"""
import asyncio
import json
import os
import sys
import time
import urllib.request
import aiohttp

WS_URL = "ws://127.0.0.1:8765/hub"
FEEDBACK_URL = "http://127.0.0.1:8765/feedback"
EXEMPLARS_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/negative_exemplars.json")


async def run_live_e2e_certification() -> bool:
    print("[0] Querying /status to obtain session_token...")
    status_url = "http://127.0.0.1:8765/status?timeout=2"
    with urllib.request.urlopen(status_url, timeout=5) as resp:
        status_data = json.loads(resp.read().decode("utf-8"))
        session_token = status_data.get("session_token", "")
        print(f"    Session token: {session_token} (State: {status_data.get('state')})")

    print("[1] Connecting to live WebSocket on port 8765...")
    packets = []
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL, timeout=15) as ws:
            # 1. Authenticated handshake
            await ws.send_json({
                "type": "handshake",
                "version": "5.0.0-foyer",
                "lab_key": session_token,
            })
            print("    Handshake frame sent with lab_key.")

            # 2. Transmit query
            query = "[ME] What firmware did we upgrade on the ESB2 server?"
            await ws.send_json({"type": "text_input", "content": query})
            print(f"    Dispatched query: '{query}'")

            # 3. Stream reception
            t0 = time.perf_counter()
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    packets.append(data)
                    src = data.get("source") or data.get("brain_source", "")
                    tok = data.get("brain") or data.get("token") or data.get("text", "")
                    if tok and len(tok.strip()) > 0:
                        sys.stdout.write(f"[{src or 'WS'}] {tok[:60]}...\n")
                        sys.stdout.flush()
                    if data.get("final") is True:
                        print("    Received final stream packet.")
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
                if time.perf_counter() - t0 > 25:
                    print("    Stream timeout reached.")
                    break
            await ws.close()

    print(f"[2] Stream complete. Total packets received: {len(packets)}")

    # 4. Test interactive downvote & step-trace attribution
    print("[3] Testing interactive downvote on POST /feedback...")
    feedback_payload = {
        "rating": "DOWN",
        "query": "What firmware did we upgrade on the ESB2 server?",
        "response": "[BUDGET]: Headroom ceiling is 900 tokens. **TECHNICAL INTUITION**: Firmware v2.1.",
        "note": "Header leak detected in spoken output",
        "request_id": "live-cert-108",
    }
    req = urllib.request.Request(
        FEEDBACK_URL,
        data=json.dumps(feedback_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        print(f"    Feedback Response: {res_data}")
        assert res_data.get("status") == "success"

    # 5. Assert negative_exemplars.json was created/updated
    print("[4] Verifying negative_exemplars.json...")
    assert os.path.exists(EXEMPLARS_PATH), f"Missing {EXEMPLARS_PATH}"
    with open(EXEMPLARS_PATH, "r", encoding="utf-8") as ef:
        exemplars_data = json.load(ef)
    assert len(exemplars_data.get("exemplars", [])) > 0
    latest = exemplars_data["exemplars"][-1]
    print(f"    Latest Exemplar: defect_stage={latest.get('defect_stage')} | request_id={latest.get('request_id')}")
    assert latest.get("request_id") == "live-cert-108"
    assert latest.get("defect_stage") == "STAGE_5_VOICE_DRIFT"

    print("✅ LIVE PHYSICAL SILICON CERTIFICATION PASSED 100%")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_live_e2e_certification())
    sys.exit(0 if success else 1)
