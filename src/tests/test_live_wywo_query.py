import asyncio
import json
import uuid
import aiohttp
import pytest


@pytest.mark.asyncio
async def test_live_wywo_query_e2e():
    """Live end-to-end WebSocket test for WYWO query on running daemon."""
    async with aiohttp.ClientSession() as session:
        async with session.get("http://127.0.0.1:8765/status?timeout=5") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data.get("vocal", False) is True, f"Lab not vocal: {data}"
            token = data.get("session_token", "")
            commit = data.get("boot_commit", "4c93027")

        ws_url = "ws://127.0.0.1:8765/"
        headers = {"X-Lab-Key": token} if token else {}
        async with session.ws_connect(ws_url, headers=headers) as ws:
            # 1. Send proper handshake
            handshake = {
                "type": "handshake",
                "version": "5.0.0-foyer",
                "client": "intercom",
                "client_commit": commit,
                "lab_key": token,
            }
            await ws.send_str(json.dumps(handshake))

            # 2. Send WYWO query
            req_id = f"live_{uuid.uuid4().hex[:6]}"
            payload = {
                "type": "text_input",
                "content": "What did you guys talk about last night?",
                "request_id": req_id,
            }
            await ws.send_str(json.dumps(payload))

            rag_eval_seen = False
            pinky_stage2_seen = False
            pinky_stage3_seen = False
            brain_seen = False
            collected_frames = []

            t0 = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - t0 < 60.0:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=25.0)
                except asyncio.TimeoutError:
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:
                    pkt = json.loads(msg.data)
                    ptype = pkt.get("type", "")
                    psrc = pkt.get("brain_source", pkt.get("source", ""))
                    pchan = pkt.get("channel", "")
                    collected_frames.append(pkt)

                    if ptype == "rag_eval":
                        rag_eval_seen = True
                        print(f"\n[LIVE WS] ✅ RAG EVAL ACCORDION: doc_id={pkt.get('doc_id')} channel={pchan} source={psrc}")
                    elif "pinky" in psrc.lower() or pchan in ("voice", "pinky"):
                        token_str = (pkt.get("token") or pkt.get("brain") or "")[:80]
                        final = pkt.get("final")
                        print(f"\n[LIVE WS] 🎙️ PINKY FRAME: source={psrc} chan={pchan} final={final} text={token_str!r}")
                        if "triage" in psrc.lower():
                            pinky_stage2_seen = True
                        if "voice" in psrc.lower() or pchan == "pinky":
                            pinky_stage3_seen = True
                    elif "brain" in psrc.lower() or pkt.get("console") == "Right":
                        brain_seen = True
                        token_str = (pkt.get("token") or pkt.get("brain") or "")[:80]
                        print(f"\n[LIVE WS] 🧠 BRAIN FRAME: source={psrc} chan={pchan} text={token_str!r}")
                    elif ptype in ("stage_progress", "crosstalk"):
                        btext = pkt.get("brain", "")
                        print(f"[LIVE WS] {btext}")
                        if "STAGE 5/5" in btext and "COMPLETED" in btext:
                            if pinky_stage3_seen or brain_seen:
                                break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break

            print(f"\n[LIVE WS SUMMARY] rag_eval={rag_eval_seen}, pinky_stage2={pinky_stage2_seen}, brain={brain_seen}, pinky_stage3={pinky_stage3_seen}")
            assert pinky_stage2_seen, f"Pinky Stage 2 opening take was not received over live WS. Frames: {collected_frames}"
            assert rag_eval_seen, f"RAG eval accordion packet was not received over live WS. Frames: {collected_frames}"
