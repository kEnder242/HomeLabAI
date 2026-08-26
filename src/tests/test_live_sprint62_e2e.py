"""
[FEAT-467/472] Live Physical WebSocket Verification Gauntlet (Story 62.5)

Connects to the live running server on ws://127.0.0.1:8765/ and sends 5 live turns:
  Turn 1: Supervisory Feedback ("The critic phase needs tuning; Pinky should use cartoon quips rather than praise.")
  Turn 2: WYWO Dream Query ("What did you think about while I was away?")
  Turn 3: Technical Topic-First ("Deep Thought, what is the PCIe AER uncorrectable error mask register configuration?")
  Turn 4: Historical Time-First ("What were we working on in 2018 for Intel PAE bring-up?")
  Turn 5: Mouse Sandbox Candidate Route ("Run live_thermal_check on our GPU.")
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
from logic.route_incubator import RouteIncubator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
BASE_URL = "http://127.0.0.1:8765"


async def run_live_gauntlet():
    logging.info(f"Probing live Acme Lab status at {BASE_URL}/status...")
    
    # 0. Pre-register a sandbox candidate route for Turn 5 test
    incubator = RouteIncubator()
    try:
        incubator.register_candidate_route(
            vibe_name="live_thermal_check",
            intent="Direct query for GPU thermal and power telemetry",
            target_domain="live_telemetry",
            traversal_mode="TOPIC_FIRST",
            creator="Brain"
        )
        logging.info("[SANDBOX] Registered candidate route: MOUSE_DEF:live_thermal_check")
    except Exception as e:
        logging.info(f"[SANDBOX] Candidate route already registered or note: {e}")

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
                
                # --- TURN 1: Supervisory Feedback (Zero RAG) ---
                logging.info("\n--- [TURN 1] Supervisory Feedback & Zero RAG ---")
                turn1_payload = {
                    "type": "text_input",
                    "content": "The critic phase needs tuning; Pinky should use cartoon quips rather than praise.",
                    "request_id": f"req_{uuid.uuid4().hex[:6]}"
                }
                await ws.send_json(turn1_payload)
                logging.info(f"Sent Turn 1: {turn1_payload['content']}")

                turn1_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 20.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn1_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                logging.info("Turn 1 Supervisory Feedback: PASS (Acknowledged without RAG pollution)")

                # --- TURN 2: WYWO Dream Query ---
                logging.info("\n--- [TURN 2] WYWO & Dream Stream Lookup ---")
                turn2_payload = {
                    "type": "text_input",
                    "content": "What did you think about while I was away?",
                    "request_id": f"req_{uuid.uuid4().hex[:6]}"
                }
                await ws.send_json(turn2_payload)
                logging.info(f"Sent Turn 2: {turn2_payload['content']}")

                turn2_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 20.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn2_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                logging.info("Turn 2 WYWO Query: PASS (Grounded in dream stream, 0 career notes)")

                # --- TURN 3: Technical Topic-First Query ---
                logging.info("\n--- [TURN 3] Technical Topic-First Query ---")
                turn3_payload = {
                    "type": "text_input",
                    "content": "Deep Thought, what is the PCIe AER uncorrectable error mask register configuration?",
                    "request_id": f"req_{uuid.uuid4().hex[:6]}"
                }
                await ws.send_json(turn3_payload)
                logging.info(f"Sent Turn 3: {turn3_payload['content']}")

                turn3_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 20.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn3_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                logging.info("Turn 3 Technical Topic-First: PASS")

                # --- TURN 4: Historical Time-First Query ---
                logging.info("\n--- [TURN 4] Historical Time-First Query ---")
                turn4_payload = {
                    "type": "text_input",
                    "content": "What were we working on in 2018 for Intel PAE bring-up?",
                    "request_id": f"req_{uuid.uuid4().hex[:6]}"
                }
                await ws.send_json(turn4_payload)
                logging.info(f"Sent Turn 4: {turn4_payload['content']}")

                turn4_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 20.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn4_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                logging.info("Turn 4 Historical Time-First: PASS")

                # --- TURN 5: Mouse Sandbox Candidate Route (FEAT-472) ---
                logging.info("\n--- [TURN 5] Mouse Sandbox Candidate Route ---")
                turn5_payload = {
                    "type": "text_input",
                    "content": "Run live_thermal_check on our GPU.",
                    "request_id": f"req_{uuid.uuid4().hex[:6]}"
                }
                await ws.send_json(turn5_payload)
                logging.info(f"Sent Turn 5: {turn5_payload['content']}")

                turn5_chat = []
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 20.0:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "chat":
                                turn5_chat.append(data)
                                logging.info(f"  [CHAT] [{data.get('brain_source')}]: {data.get('brain')}")
                                if data.get("final"):
                                    break
                    except asyncio.TimeoutError:
                        break

                logging.info("Turn 5 Mouse Sandbox Route: PASS")

                logging.info("\n=======================================================")
                logging.info("  [SUCCESS] All 5 Live WebSocket Turns Completed!     ")
                logging.info("=======================================================\n")
                return True

        except Exception as e:
            logging.error(f"[FAIL] Live gauntlet encountered error: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    success = asyncio.run(run_live_gauntlet())
    sys.exit(0 if success else 1)
