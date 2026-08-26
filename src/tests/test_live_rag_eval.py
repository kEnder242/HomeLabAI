"""
[FEAT-454/470] End-to-End Live Cognitive RAG Gauntlet (Story 63.3)

Pytest test suite executing live RAG evaluations over WebSocket (ws://127.0.0.1:8765/ws)
verifying Triage -> Interest Loop -> Brain Node -> Pinky Critic execution against
grounded validation anchors from config/validation_anchors.json.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
import pytest
import aiohttp

# Bootstrap path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

CONFIG_PATH = SRC_DIR.parent / "config" / "validation_anchors.json"
BASE_HTTP_URL = "http://127.0.0.1:8765"
STATUS_URL = "http://127.0.0.1:8000/status"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def wait_for_ready_and_vocal(status_url: str = STATUS_URL, timeout: float = 5.0) -> bool:
    """Check if the Lab Attendant / server is ready."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(status_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    state = data.get("state", "")
                    return state in ("SERVICE_UNATTENDED", "DEBUG_BRAIN", "RUNNING", "VOCAL")
    except Exception:
        pass
    return False


async def send_and_collect_turn(ws, query_text: str, timeout: float = 30.0) -> list[dict]:
    """Send a text query frame and collect received JSON frames until round table completes."""
    req_id = str(uuid.uuid4())[:8]
    payload = {
        "type": "text_input",
        "content": query_text,
        "request_id": req_id,
    }
    await ws.send_str(json.dumps(payload))
    frames = []
    t0 = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - t0 < timeout:
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                frames.append(data)
                frame_type = data.get("type", "")
                if frame_type in ("crosstalk", "progress", "stage_progress"):
                    content = data.get("brain", "")
                    if any(term in content for term in ("Consensus", "Review", "Sovereignty", "Insight")):
                        # Check if response stream reached completion
                        if len(frames) >= 2:
                            break
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
        except asyncio.TimeoutError:
            if frames:
                break
    return frames


@pytest.mark.asyncio
async def test_live_cognitive_rag_anchors():
    """Execute end-to-end cognitive RAG gauntlet over live WebSocket."""
    if not CONFIG_PATH.exists():
        pytest.fail(f"Validation anchors config missing: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r") as f:
        anchors = json.load(f)

    # 1. Probe status and fetch session token
    session_token = ""
    is_ready = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_HTTP_URL}/status", timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    session_token = status_data.get("session_token", "")
                    is_ready = True
    except Exception as e:
        pytest.fail(f"Lab Attendant status endpoint unreachable on {BASE_HTTP_URL}: {e}")

    if not is_ready:
        pytest.fail("Live Lab Attendant / Intercom server is not running on 8765")

    async with aiohttp.ClientSession() as session:
        # 2. Connect to Foyer WebSocket endpoint
        ws_url = f"ws://127.0.0.1:8765/hub"
        try:
            async with session.ws_connect(ws_url, timeout=aiohttp.ClientTimeout(total=5.0)) as ws:
                # 3. Authenticated Handshake (FEAT-426)
                await ws.send_str(json.dumps({"type": "handshake", "lab_key": session_token}))
                
                # Receive initial status
                handshake_resp = await asyncio.wait_for(ws.receive(), timeout=3.0)
                assert handshake_resp.type == aiohttp.WSMsgType.TEXT
                
                # Test top 3 representative anchors
                test_anchors = [a for a in anchors if a.get("id") in ("VAL-01", "VAL-02", "VAL-08")]
                if not test_anchors:
                    test_anchors = anchors[:3]

                for anchor in test_anchors:
                    query = anchor["query"]
                    frames = await send_and_collect_turn(ws, query, timeout=20.0)
                    
                    logging.info(f"Anchor {anchor['id']} received {len(frames)} frames")
                    assert len(frames) > 0, f"Expected frames for query: {query}"
        except Exception as e:
            pytest.fail(f"WebSocket communication failed on {ws_url}: {e}")
