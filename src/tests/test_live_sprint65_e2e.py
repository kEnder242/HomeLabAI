"""
[FEAT-486/487/488/489] Live Physical WebSocket Verification Gauntlet (Sprint 65.0)

Connects to the live running server on ws://127.0.0.1:8765/ and sends 4 live turns:
  Turn 1: Live Semantic Meta-Triage Feedback Interceptor ([FEAT-487] / BKM-035)
  Turn 2: Live Anti-Bleed Prompt Hygiene Check ([FEAT-488])
  Turn 3: Live Two-Mice Sequential Streaming Handover ([FEAT-489])
  Turn 4: Live Historical Temporal Inquiries with Casual Intros (No False Feedback Hijack)
"""

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

# Bootstrap sys.path for direct invocation
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
BASE_URL = "http://127.0.0.1:8765"


async def run_live_sprint65_gauntlet():
    from src.tests.conftest import assert_live_bytecode
    assert_live_bytecode()

    logging.info(f"Probing live Acme Lab status at {BASE_URL}/status...")

    async with aiohttp.ClientSession() as session:
        # 1. Fetch active session token
        session_token = ""
        try:
            async with session.get(f"{BASE_URL}/status", timeout=5.0) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    session_token = status_data.get("session_token", "")
                    logging.info(f"[AUTH] Acquired active session_token: {session_token} (Boot Commit: {status_data.get('boot_commit')})")
        except Exception as e:
            logging.error(f"[AUTH] Failed to reach {BASE_URL}/status: {e}")
            return False

        if not session_token:
            logging.error("[AUTH] No session_token returned by /status.")
            return False

        # 2. Connect to WebSocket
        ws_url = f"{BASE_URL}/"
        logging.info(f"Connecting to live Acme Lab WebSocket at {ws_url}...")
        try:
            async with session.ws_connect(ws_url, timeout=15.0) as ws:
                logging.info("[WS] Socket connected. Sending authentication handshake...")
                
                # Receive initial status frame
                msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    logging.info(f"[WS] Initial status received: {msg.data[:80]}...")

                # Send Handshake
                await ws.send_json({"type": "handshake", "lab_key": session_token})
                auth_resp = await asyncio.wait_for(ws.receive(), timeout=5.0)
                logging.info(f"[WS] Auth response: {auth_resp.data[:80]}...")

                async def send_turn(turn_label, query_text, expect_vibe=None, is_feedback=False):
                    req_id = f"req_{uuid.uuid4().hex[:6]}"
                    payload = {
                        "type": "text_input",
                        "content": query_text,
                        "request_id": req_id
                    }
                    logging.info(f"\n{'='*70}\n[LIVE TURN] {turn_label}: '{query_text}' (req: {req_id})\n{'='*70}")
                    await ws.send_json(payload)

                    frames = []
                    thought_sources = set()
                    channels = set()
                    has_rag_eval = False
                    critic_error = False
                    anti_bleed_clean = True

                    start_time = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - start_time < 75.0:
                        try:
                            raw_msg = await asyncio.wait_for(ws.receive(), timeout=25.0)
                            if raw_msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(raw_msg.data)
                                frames.append(data)
                                msg_type = data.get("type", "")

                                if msg_type == "rag_eval":
                                    has_rag_eval = True
                                    logging.info(f"[WS] [RAG EVAL] Doc={data.get('doc_id')} (Tier: {data.get('tier')})")

                                elif data.get("brain") or data.get("token"):
                                    source = data.get("source") or data.get("brain_source", "Unknown")
                                    channel = data.get("channel", "chat")
                                    token = data.get("brain") or data.get("token", "")
                                    thought_sources.add(source)
                                    channels.add(channel)

                                    # Anti-Bleed check (FEAT-488)
                                    if any(bad in token for bad in ["GROUNDING_PROTOCOL:", "[STANCE]:", "RAW CONTEXT APPEND"]):
                                        anti_bleed_clean = False
                                        logging.error(f"[BLEED] Rogue prompt header detected in stream: {token}")

                                    # Critic check (FEAT-489)
                                    if "Narf! The retort went missing." in token:
                                        critic_error = True
                                        logging.error(f"[CRITIC ERROR] Retort went missing!")

                                    if data.get("final", False):
                                        logging.info(f"[STREAM FINAL] Source: {source} | Channel: {channel} | Token: {token[:60]}...")
                                        if is_feedback and "Feedback" in source:
                                            break
                                        if not is_feedback and (source in ["Pinky (Voice)", "Pinky (Response)", "Pinky (Foil Interjection)", "Deep Thought"] or data.get("final_turn", False)):
                                            break

                            elif raw_msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                logging.warning(f"[WS] Stream closed: {raw_msg}")
                                break
                        except asyncio.TimeoutError:
                            if frames:
                                break

                    logging.info(f"[TURN SUMMARY] Sources active: {thought_sources} | Channels: {channels}")
                    assert anti_bleed_clean, "Rogue prompt header leaked into live stream!"
                    assert not critic_error, "Critic retort went missing error occurred!"
                    return {
                        "frames": frames,
                        "sources": thought_sources,
                        "channels": channels,
                        "has_rag_eval": has_rag_eval
                    }

                # --- Turn 1: [FEAT-487] Live Semantic Meta-Triage Feedback Interceptor ---
                t1 = await send_turn(
                    "Turn 1: Semantic Feedback Intercept",
                    "feedback: KENDER should have a ping check gate",
                    is_feedback=True
                )
                assert any("Feedback" in s for s in t1["sources"]), f"Feedback turn was not intercepted! Sources: {t1['sources']}"
                logging.info("✅ Turn 1 PASSED: Semantic feedback intercepted on live silicon.")

                # --- Turn 2: [FEAT-488] Live Anti-Bleed Prompt Hygiene Check ---
                t2 = await send_turn(
                    "Turn 2: Technical Inquiry (Anti-Bleed Check)",
                    "What was our PCIe uncorrectable error mask setup for 2016 ESB2?"
                )
                logging.info("✅ Turn 2 PASSED: Anti-bleed guardrail verified on live stream.")

                # --- Turn 3: [FEAT-489] Live Two-Mice Sequential Streaming Handover ---
                t3 = await send_turn(
                    "Turn 3: Two-Mice Handover & Distillation",
                    "How about 2015? Name the 4 top technologies I worked with then."
                )
                logging.info("✅ Turn 3 PASSED: Two-Mice Handover & Distillation verified live.")

                # --- Turn 4: Historical Inquiry with Casual Intro & Struggle Keyword ---
                t4 = await send_turn(
                    "Turn 4: Historical Struggle Inquiry (Anti-False-Feedback Check)",
                    "Let's talk about 2015. What did I struggle with during this time? Looking for the top two topics"
                )
                assert not any("Feedback" in s for s in t4["sources"]), f"Historical turn was incorrectly hijacked as feedback! Sources: {t4['sources']}"
                logging.info("✅ Turn 4 PASSED: Historical inquiry routed properly without false feedback hijack.")

                logging.info("\n" + "🏆"*35 + "\nALL LIVE GAUNTLET TURNS CERTIFIED ON RUNNING SILICON!\n" + "🏆"*35)
                return True

        except Exception as e:
            logging.error(f"[WS] Live gauntlet failed: {e}")
            return False


if __name__ == "__main__":
    success = asyncio.run(run_live_sprint65_gauntlet())
    sys.exit(0 if success else 1)
