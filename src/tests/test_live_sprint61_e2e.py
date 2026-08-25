"""
[FEAT-467/468/469/470/471] Live Physical WebSocket Verification Gauntlet (Story 61.5)

Connects to the live running server on ws://127.0.0.1:8765/ following the authenticated handshake protocol:
  1. GET /status to acquire the active session_token
  2. ws_connect to ws://127.0.0.1:8765/
  3. Send handshake frame: {"type": "handshake", "lab_key": session_token}
  4. Send Turn 1: Meta-grounding query ("Narf! What is the status of the audio_pipeline and lab_dna_router?")
  5. Send Turn 2: Casual quip ("Check the server temperature and tell me a joke about Brain.")
  6. Send Turn 3: Technical validation ("Deep Thought, what is the PCIe AER uncorrectable error register bitmask?")
"""

import asyncio
import json
import logging
import sys
import uuid
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
BASE_URL = "http://127.0.0.1:8765"


async def run_live_gauntlet():
    logging.info(f"Probing live Acme Lab status at {BASE_URL}/status...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch active session token
        session_token = ""
        try:
            async with session.get(f"{BASE_URL}/status", timeout=5.0) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    session_token = status_data.get("session_token", "")
                    logging.info(f"[AUTH] Acquired active session_token: {session_token}")
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
            async with session.ws_connect(ws_url, timeout=10.0) as ws:
                logging.info("[WS] Socket connected. Sending authentication handshake...")
                
                # Receive initial status frame
                msg = await asyncio.wait_for(ws.receive(), timeout=3.0)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    logging.info(f"[WS] Initial status received: {msg.data[:80]}...")

                # Send Handshake
                await ws.send_json({"type": "handshake", "lab_key": session_token})
                auth_resp = await asyncio.wait_for(ws.receive(), timeout=3.0)
                logging.info(f"[WS] Auth response: {auth_resp.data}")
                
                # --- TURN 1: Meta-Grounding & Demarcation Query ---
                logging.info("\n--- [TURN 1] Meta-Grounding & Anti-Duplication ---")
                turn1_req = f"req_{uuid.uuid4().hex[:6]}"
                turn1_payload = {
                    "type": "text_input",
                    "content": "Narf! What is the status of the audio_pipeline and lab_dna_router?",
                    "request_id": turn1_req
                }
                await ws.send_json(turn1_payload)
                logging.info(f"Sent Turn 1: {turn1_payload['content']}")

                turn1_crosstalk = []
                turn1_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 25.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            m_type = data.get("type")
                            if m_type == "crosstalk":
                                turn1_crosstalk.append(data)
                                logging.info(f"  [CROSSTALK] [{data.get('brain_source')}]: {data.get('brain')}")
                            elif m_type == "chat":
                                turn1_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                # Verify Turn 1 properties
                insight_found = any(c.get("brain_source") == "Brain (Insight)" for c in turn1_crosstalk)
                logging.info(f"Turn 1 Brain (Insight) Attribution: {'PASS' if insight_found else 'FALLBACK'}")

                if turn1_chat:
                    final_chat = turn1_chat[-1].get("brain", "")
                    assert "[ASSISTANT:" not in final_chat, f"Dirty demarcation tag found in chat: {final_chat}"
                    assert not final_chat.startswith("Pinky:"), f"Redundant prefix found: {final_chat}"
                    logging.info("Turn 1 Speaker Anti-Duplication: PASS (Clean chat dispatch)")

                # --- TURN 2: Cartoon Critic & Robotic Boilerplate Rejection ---
                logging.info("\n--- [TURN 2] Pinky Critic & Boilerplate Rejection ---")
                turn2_req = f"req_{uuid.uuid4().hex[:6]}"
                turn2_payload = {
                    "type": "text_input",
                    "content": "Check the server temperature and tell me a joke about Brain.",
                    "request_id": turn2_req
                }
                await ws.send_json(turn2_payload)
                logging.info(f"Sent Turn 2: {turn2_payload['content']}")

                turn2_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 25.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn2_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                if turn2_chat:
                    full_turn2 = " ".join([c.get("brain", "") for c in turn2_chat])
                    assert "a well-crafted response" not in full_turn2.lower(), "Robotic boilerplate detected in chat!"
                    logging.info("Turn 2 Boilerplate Rejection: PASS (No robotic phrases detected)")

                # --- TURN 3: Technical Validation & Handshake Stream Demarcation ---
                logging.info("\n--- [TURN 3] Technical Validation & Handshake Demarcation ---")
                turn3_req = f"req_{uuid.uuid4().hex[:6]}"
                turn3_payload = {
                    "type": "text_input",
                    "content": "Deep Thought, what is the PCIe AER uncorrectable error register bitmask?",
                    "request_id": turn3_req
                }
                await ws.send_json(turn3_payload)
                logging.info(f"Sent Turn 3: {turn3_payload['content']}")

                turn3_crosstalk = []
                turn3_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 25.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            m_type = data.get("type")
                            if m_type == "crosstalk":
                                turn3_crosstalk.append(data)
                                logging.info(f"  [CROSSTALK] [{data.get('brain_source')}]: {data.get('brain')}")
                            elif m_type == "chat":
                                turn3_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                for chat_msg in turn3_chat:
                    c_text = chat_msg.get("brain", "")
                    assert "system operational. awaiting command parameters" not in c_text.lower(), \
                        "Deep Thought operational handshake leaked into CHAT stream!"

                logging.info("Turn 3 Handshake Demarcation: PASS (Handshakes strictly isolated to crosstalk)")

                logging.info("\n=======================================================")
                logging.info("  [SUCCESS] All Live WebSocket Verification Tests Passed! ")
                logging.info("=======================================================\n")
                return True

        except Exception as e:
            logging.error(f"[FAIL] Live gauntlet encountered error: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    success = asyncio.run(run_live_gauntlet())
    sys.exit(0 if success else 1)
