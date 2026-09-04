import pytest
import asyncio
import json
import time
import requests
import websockets
import subprocess
from tests.conftest import assert_live_bytecode

import os

def _get_local_commit():
    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    res = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=repo_dir, capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else "unknown"

@pytest.mark.asyncio
async def test_live_lab_fresh_bytecode_gate():
    """Verify live integrity gate catches commit mismatch without restarting the lab."""
    assert_live_bytecode()

@pytest.mark.asyncio
async def test_live_handshake_rejects_stale_client_commit():
    """Verify server actively rejects connections sending mismatched client_commit."""
    status = requests.get("http://127.0.0.1:8765/status", timeout=2).json()
    lab_key = status.get("session_token", "")
    
    uri = "ws://127.0.0.1:8765"
    # Connect with a purposely bogus client_commit
    async with websockets.connect(uri, additional_headers={"X-Lab-Key": lab_key}) as ws:
        await ws.send(json.dumps({
            "type": "handshake",
            "client": "live_test",
            "client_commit": "deadbeef",
            "lab_key": lab_key
        }))
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
        except websockets.exceptions.ConnectionClosed as e:
            assert e.code == 1008, f"Expected WS 1008 Close code, got {e.code}"

@pytest.mark.asyncio
async def test_live_sprint71_dialogue_roll_up():
    """Live Fire end-to-end dialogue test for Sprint 71 stability fixes."""
    assert_live_bytecode()
    
    local_commit = _get_local_commit()
    status = requests.get("http://127.0.0.1:8765/status", timeout=2).json()
    lab_key = status.get("session_token", "")
    
    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(
        uri, 
        additional_headers={"X-Lab-Key": lab_key, "X-Client-Commit": local_commit}
    ) as ws:
        await ws.send(json.dumps({
            "type": "handshake", 
            "client": "live_test", 
            "client_commit": local_commit,
            "lab_key": lab_key
        }))
        
        # Drain initial status frame
        init_frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        assert init_frame.get("state") in ["ready", "connected", "init", "OPERATIONAL"]

        # Send dialogue turn
        await ws.send(json.dumps({"type": "text_input", "content": "hello pinky!"}))
        
        # Monitor turn stream for Pinky response (give 90s for full multi-node resolution)
        t0 = time.time()
        found_pinky = False
        received_msgs = []
        while time.time() - t0 < 90.0:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                msg = json.loads(raw)
                received_msgs.append(msg)
                source = msg.get("brain_source", "")
                text = msg.get("brain", "")
                if ("Pinky" in source or "Pinky" in msg.get("source", "")) and not "HyDE" in source and not "Triage" in source:
                    found_pinky = True
                    break
            except asyncio.TimeoutError:
                continue
                
        assert found_pinky, f"Pinky must respond as lead node. Received frames: {received_msgs}"
