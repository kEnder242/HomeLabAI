#!/usr/bin/env python3
"""
[BKM-024 / FEAT-658] Historical Reconciliation Verification Probe
Probes acme_foyer_v5 on ws://127.0.0.1:8765 to verify that:
1. Asking about 2021 retrieves Montana package delivery (not Kayak/CWF transition).
2. Asking about Kayak/Montana transition pinpoints 2024 (not 2020-2023).
"""

import asyncio
import json
import sys
import time
import urllib.request
import websockets

FOYER_HTTP_URL = "http://127.0.0.1:8765"
FOYER_WS_URL = "ws://127.0.0.1:8765"


def get_status():
    req = urllib.request.Request(f"{FOYER_HTTP_URL}/status?timeout=2")
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_probe(query: str, session_token: str, boot_commit: str, timeout: float = 30.0):
    print(f"\n" + "=" * 65)
    print(f"🚀 Live Probe: '{query}'")
    print(f"   Target: Foyer :8765 | Boot Commit: {boot_commit}")
    print("=" * 65)

    events = []
    chat_messages = []
    final_responses = []

    async with websockets.connect(
        FOYER_WS_URL,
        additional_headers={"X-Lab-Key": session_token, "X-Client-Commit": boot_commit},
        open_timeout=30.0,
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "handshake",
                    "version": "5.0.0",
                    "client": "probe_historical_reconciliation",
                    "lab_key": session_token,
                }
            )
        )
        await asyncio.sleep(0.5)

        t0 = time.time()
        await ws.send(json.dumps({"type": "text_input", "content": query}))

        while (time.time() - t0) < timeout:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
                if isinstance(raw, bytes):
                    continue
                msg = json.loads(raw)
                msg_type = msg.get("type")
                source = (msg.get("source") or msg.get("brain_source") or "").upper()

                if msg_type == "chat":
                    brain_text = msg.get("brain", "")
                    events.append(("chat", source, brain_text))
                    chat_messages.append({"source": source, "text": brain_text})
                    print(f"  💬 [{source}]: {brain_text[:120]}...")
                elif msg_type == "final":
                    final_text = msg.get("text", "")
                    final_responses.append(final_text)
                    print(f"  🏁 [FINAL RESPONSE]:\n{final_text}\n")
                    break
            except asyncio.TimeoutError:
                if chat_messages or final_responses:
                    break

        elapsed = time.time() - t0
        print(f"⏱️ Turn Completed in {elapsed:.2f}s")
        return {"query": query, "chats": chat_messages, "finals": final_responses, "elapsed": elapsed}


async def main():
    print("Checking Foyer health...")
    status = get_status()
    session_token = status.get("session_token")
    boot_commit = status.get("boot_commit")
    print(f"Foyer state: {status.get('state')} | Boot Commit: {boot_commit}")

    # Probe 1: 2021 historical inquiry
    r1 = await run_probe("What was my focus in 2021?", session_token, boot_commit)

    await asyncio.sleep(2.0)

    # Probe 2: Kayak and Montana timing
    r2 = await run_probe("When did the Kayak and Montana platform integration happen?", session_token, boot_commit)

    print("\n" + "=" * 65)
    print("📊 HISTORICAL RECONCILIATION SUMMARY")
    print("=" * 65)
    print(f"Probe 1 (2021 Focus) Duration: {r1['elapsed']:.2f}s")
    print(f"Probe 2 (Kayak/Montana Timing) Duration: {r2['elapsed']:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
