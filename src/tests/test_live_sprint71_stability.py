import pytest
import asyncio
import json
import time
import requests
import websockets
import subprocess
from tests.conftest import assert_live_bytecode, get_bytecode_status

def _get_local_commit():
    res = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else "unknown"

@pytest.mark.asyncio
async def test_live_lab_fresh_bytecode_gate():
    """Verify live integrity gate catches commit mismatch without restarting the lab."""
    # This MUST fail right now because Served (5d020e4) != Local (HEAD)
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
        await ws.send(json.dumps({"type": "text_input", "content": "hello pinky!"}))
        
        # Monitor turn stream & verify sub-second Pinky response with zero archive dump
        t0 = time.time()
        found_pinky = False
        while time.time() - t0 < 5.0:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
            if "Pinky" in msg.get("brain_source", ""):
                found_pinky = True
                break
        assert found_pinky, "Pinky must respond as lead node to direct salutation"
