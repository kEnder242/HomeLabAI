#!/usr/bin/env python3
import asyncio
import json
import time
import urllib.request
import websockets

FOYER_HTTP = "http://127.0.0.1:8765"
FOYER_WS = "ws://127.0.0.1:8765"


def get_status():
    req = urllib.request.Request(f"{FOYER_HTTP}/status?timeout=2")
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def test_query(prompt: str):
    status = get_status()
    session_token = status.get("session_token")
    boot_commit = status.get("boot_commit")

    print(f"\n=======================================================")
    print(f"🔬 Prompt: '{prompt}'")
    print(f"=======================================================")

    tokens = {"PINKY": [], "BRAIN": [], "THOUGHT": []}
    chat_msgs = []

    async with websockets.connect(
        FOYER_WS,
        additional_headers={"X-Lab-Key": session_token, "X-Client-Commit": boot_commit},
        open_timeout=30.0,
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "handshake",
                    "version": "5.0.0",
                    "client": "test_waterfall_reconciliation",
                    "lab_key": session_token,
                }
            )
        )
        await asyncio.sleep(0.5)

        t0 = time.time()
        await ws.send(json.dumps({"type": "text_input", "content": prompt}))

        while (time.time() - t0) < 40.0:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if isinstance(raw, bytes):
                    continue
                msg = json.loads(raw)
                mtype = msg.get("type")
                source = (msg.get("source") or msg.get("brain_source") or "").upper()

                if mtype == "thought_stream":
                    tok = msg.get("token", "")
                    for n in tokens:
                        if n in source:
                            tokens[n].append(tok)
                elif mtype == "chat":
                    text = msg.get("brain", "")
                    chat_msgs.append((source, text))
            except asyncio.TimeoutError:
                if any(tokens.values()) or chat_msgs:
                    break

        elapsed = time.time() - t0
        print(f"Turn Duration: {elapsed:.2f}s")
        for n in ["PINKY", "BRAIN", "THOUGHT"]:
            content = "".join(tokens[n]).strip()
            if content:
                print(f"\n--- {n} STREAM ---")
                print(content[:500])

        for s, txt in chat_msgs:
            print(f"\n💬 [{s} CHAT]:\n{txt[:400]}")


async def main():
    await test_query("[ME] What was my primary technical focus in 2021?")
    await asyncio.sleep(2.0)
    await test_query("[ME] When did the Kayak and Montana transition happen?")


if __name__ == "__main__":
    asyncio.run(main())
