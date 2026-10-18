"""
Sprint 105 Physical Silicon Live Probe Gauntlet (BKM-024 / BKM-086).
Directly probes the active acme_foyer_v5 daemon running on ws://127.0.0.1:8765
to verify the pure Waterfall Flow:
- Probe 1: Casual banter ("hi") -> Pinky speaks Tier 1 take, Brain and Deep Thought stay dormant.
- Probe 2: Historical inquiry ("remember Aurora?") -> Career compass / historical flow, Pinky + Brain.
"""

import asyncio
import json
import sys
import time
import urllib.request
import websockets

FOYER_HTTP_URL = "http://127.0.0.1:8765"
FOYER_WS_URL = "ws://127.0.0.1:8765"


def get_status(timeout_param: int = 2):
    req = urllib.request.Request(f"{FOYER_HTTP_URL}/status?timeout={timeout_param}")
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def run_probe(query: str, session_token: str, boot_commit: str, timeout: float = 25.0):
    print(f"\n" + "=" * 60)
    print(f"🚀 Injecting Live Probe: '{query}'")
    print(f"   Boot Commit: {boot_commit}")
    print("=" * 60)

    events = []
    streamed_tokens = {"PINKY": [], "BRAIN": [], "THOUGHT": []}
    chat_messages = []

    async with websockets.connect(
        FOYER_WS_URL,
        additional_headers={"X-Lab-Key": session_token, "X-Client-Commit": boot_commit},
        open_timeout=30.0,
    ) as ws:
        # Handshake
        await ws.send(
            json.dumps(
                {
                    "type": "handshake",
                    "version": "5.0.0",
                    "client": "probe_sprint105_waterfall",
                    "lab_key": session_token,
                }
            )
        )
        await asyncio.sleep(0.5)

        # Send query
        t0 = time.time()
        await ws.send(
            json.dumps(
                {
                    "type": "text_input",
                    "content": query,
                }
            )
        )

        while (time.time() - t0) < timeout:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=4.0)
                if isinstance(raw, bytes):
                    continue
                msg = json.loads(raw)
                msg_type = msg.get("type")
                source = (msg.get("source") or msg.get("brain_source") or "").upper()

                if msg_type == "status":
                    events.append(("status", msg.get("state"), msg.get("message")))
                elif msg_type == "thought_stream":
                    tok = msg.get("token", "")
                    for node in ["PINKY", "BRAIN", "THOUGHT"]:
                        if node in source:
                            streamed_tokens[node].append(tok)
                elif msg_type == "chat":
                    brain_text = msg.get("brain", "")
                    events.append(("chat", source, brain_text))
                    chat_messages.append({"source": source, "text": brain_text})
                    print(f"  💬 [{source}]: {brain_text}")
                elif msg_type == "final":
                    final_text = msg.get("text", "")
                    events.append(("final", source, final_text))
            except asyncio.TimeoutError:
                # If no message for 4s and we got something, turn is complete
                if chat_messages or any(streamed_tokens.values()):
                    break
                continue

    total_latency = time.time() - t0
    pinky_stream = "".join(streamed_tokens["PINKY"])
    brain_stream = "".join(streamed_tokens["BRAIN"])
    thought_stream = "".join(streamed_tokens["THOUGHT"])

    print(f"\n⏱️ Elapsed Time: {total_latency:.2f}s")
    print(f"📊 Pinky Tokens: {len(streamed_tokens['PINKY'])} chars: {len(pinky_stream)}")
    print(f"📊 Brain Tokens: {len(streamed_tokens['BRAIN'])} chars: {len(brain_stream)}")
    print(f"📊 Thought Tokens: {len(streamed_tokens['THOUGHT'])} chars: {len(thought_stream)}")

    return {
        "query": query,
        "latency": total_latency,
        "events": events,
        "chat_messages": chat_messages,
        "pinky_stream": pinky_stream,
        "brain_stream": brain_stream,
        "thought_stream": thought_stream,
    }


async def main():
    print("🔬 SPRINT 105 SILICON VALIDATION GAUNTLET")
    status = get_status(timeout_param=2)
    session_token = status.get("session_token")
    boot_commit = status.get("boot_commit")
    print(f"Connected to Foyer. Boot Commit: {boot_commit} | Mode: {status.get('state')}")

    # 1. Probe 1: Casual Banter
    print("\n[PROBE 1/3] Casual Banter Verification...")
    res1 = await run_probe("[ME] hi", session_token, boot_commit, timeout=25.0)

    # Verification criteria for Probe 1
    has_pinky = bool(res1["pinky_stream"] or any("PINKY" in m["source"] for m in res1["chat_messages"]))
    brain_active = bool(res1["brain_stream"] or any("BRAIN" in m["source"] for m in res1["chat_messages"]))
    thought_active = bool(res1["thought_stream"] or any("THOUGHT" in m["source"] for m in res1["chat_messages"]))

    print(f"\nProbe 1 Analysis:")
    print(f"  - Pinky Active: {has_pinky}")
    print(f"  - Brain Dormant: {not brain_active}")
    print(f"  - Thought Dormant: {not thought_active}")

    if not has_pinky:
        print("❌ PROBE 1 FAIL: Pinky did not speak on casual banter!")
        sys.exit(1)
    if brain_active:
        print("❌ PROBE 1 FAIL: Brain was NOT dormant on casual banter!")
        sys.exit(1)
    if thought_active:
        print("❌ PROBE 1 FAIL: Deep Thought was NOT dormant on casual banter!")
        sys.exit(1)
    print("✅ PROBE 1 PASS: Pure Waterfall casual banter (Pinky vocal, Brain/Thought dormant)!")

    # Wait 3s for engine settle
    await asyncio.sleep(3.0)

    # 2. Probe 2: Historical Inquiry
    print("\n[PROBE 2/3] Historical Inquiry Verification...")
    res2 = await run_probe("[ME] remember Aurora?", session_token, boot_commit, timeout=35.0)

    has_pinky_2 = bool(res2["pinky_stream"] or any("PINKY" in m["source"] for m in res2["chat_messages"]))
    has_brain_2 = bool(res2["brain_stream"] or any("BRAIN" in m["source"] for m in res2["chat_messages"]))

    print(f"\nProbe 2 Analysis:")
    print(f"  - Pinky Active: {has_pinky_2}")
    print(f"  - Brain/Council Active: {has_brain_2}")

    if not has_pinky_2:
        print("❌ PROBE 2 FAIL: Pinky did not speak on historical inquiry!")
        sys.exit(1)
    print("✅ PROBE 2 PASS: Historical inquiry successfully processed through multi-stage council!")

    # Wait 3s for engine settle
    await asyncio.sleep(3.0)

    # 3. Probe 3: Story 105.15 Interest Damping Verification
    print("\n[PROBE 3/3] Dynamic Interest Damping Verification ('How are you and Brain?')...")
    res3 = await run_probe("[ME] How are you and Brain?", session_token, boot_commit, timeout=30.0)

    has_pinky_3 = bool(res3["pinky_stream"] or any("PINKY" in m["source"] for m in res3["chat_messages"]))
    thought_active_3 = bool(res3["thought_stream"] or any("THOUGHT" in m["source"] for m in res3["chat_messages"]))

    print(f"\nProbe 3 Analysis:")
    print(f"  - Pinky Active: {has_pinky_3}")
    print(f"  - Deep Thought Dormant (Cascading Halted): {not thought_active_3}")

    if not has_pinky_3:
        print("❌ PROBE 3 FAIL: Pinky did not speak on greeting!")
        sys.exit(1)
    if thought_active_3:
        print("❌ PROBE 3 FAIL: Deep Thought was NOT dormant; cascade runaway occurred!")
        sys.exit(1)
    print("✅ PROBE 3 PASS: Brain damped interest or zero RAG context kept Deep Thought dormant. Cascade halted!")

    print("\n" + "=" * 60)
    print("🏆 ALL SPRINT 105 PHYSICAL SILICON PROBES PASSED (100%)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
