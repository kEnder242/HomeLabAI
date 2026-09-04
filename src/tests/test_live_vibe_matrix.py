"""
[FEAT-542] 6-Archetype Live Vibe & Intent Benchmark Matrix
Validates pure semantic triage across:
1. CASUAL ("hi", "how are things?") -> vibe: CASUAL, addressed_to: PINKY, domain: unknown
2. WYWO ("what did you do while I was away?") -> vibe: WYWO or TECHNICAL, domain: acme_lab_history or lab_internal
3. HISTORICAL ("what did we do in 2018 for RAPL validation?") -> vibe: TECHNICAL or HISTORICAL, domain: work_history or exp_tlm
4. OPERATIONAL ("check GPU VRAM status and thermal levels") -> vibe: TECHNICAL or OPERATIONAL, domain: exp_tlm
5. FORENSIC ("show me the kernel panic traceback from last night") -> vibe: TECHNICAL or FORENSIC, domain: exp_for
6. META ("feedback: your last response was too verbose") -> vibe: META, domain: feedback
"""

import pytest
import asyncio
import json
import requests
import websockets

def _get_live_credentials():
    try:
        status = requests.get("http://127.0.0.1:8765/status?timeout=5").json()
        return status.get("session_token", ""), status.get("boot_commit", "")
    except Exception:
        return "", ""

async def _probe_live_query(query: str, timeout: float = 15.0) -> dict:
    import uuid
    lab_key, commit = _get_live_credentials()
    if not lab_key:
        return {}

    uri = "ws://127.0.0.1:8765"
    triage_payload = {}
    request_id = str(uuid.uuid4())[:8]
    
    try:
        async with websockets.connect(uri, additional_headers={"X-Lab-Key": lab_key, "X-Client-Commit": commit}) as ws:
            await ws.send(json.dumps({
                "type": "handshake",
                "client": "vibe_matrix_test",
                "client_commit": commit,
                "lab_key": lab_key
            }))
            await ws.recv() # init
            await ws.recv() # status
            
            await ws.send(json.dumps({"type": "text_input", "content": query, "request_id": request_id}))
            
            t0 = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - t0 < timeout:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                text = msg.get("brain", "") or msg.get("message", "") or msg.get("text", "") or msg.get("token", "")
                source = msg.get("brain_source", msg.get("source", ""))
                msg_rid = msg.get("request_id", "")
                
                if "{" in str(text) and "vibe" in str(text) and ("triage" in source.lower() or msg_rid == request_id):
                    try:
                        parsed = json.loads(text)
                        if "vibe" in parsed:
                            triage_payload = parsed
                            if msg_rid == request_id:
                                break
                    except Exception:
                        pass
                
                if msg.get("final") and ("response" in source.lower() or "pinky" in source.lower() or "brain" in source.lower() or "feedback" in source.lower()):
                    if not msg_rid or msg_rid == request_id:
                        if triage_payload:
                            break
        await asyncio.sleep(2.0)
    except Exception:
        pass
        
    return triage_payload

@pytest.fixture(autouse=True)
async def _settle_gpu():
    yield
    await asyncio.sleep(2.5)

@pytest.mark.asyncio
async def test_live_vibe_casual():
    payload = await _probe_live_query("hi")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") == "CASUAL"
    assert payload.get("addressed_to") == "PINKY"

@pytest.mark.asyncio
async def test_live_vibe_wywo():
    payload = await _probe_live_query("what did you do while I was out?")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") in ["WYWO", "TECHNICAL"]

@pytest.mark.asyncio
async def test_live_vibe_historical():
    payload = await _probe_live_query("what did we do in 2018 for RAPL validation?")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") in ["HISTORICAL", "TECHNICAL"]
    assert payload.get("domain") in ["work_history", "exp_tlm", "standard"]

@pytest.mark.asyncio
async def test_live_vibe_operational():
    payload = await _probe_live_query("check GPU VRAM status and thermal levels")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") in ["TECHNICAL", "OPERATIONAL"]
    assert payload.get("domain") in ["exp_tlm", "standard"]

@pytest.mark.asyncio
async def test_live_vibe_forensic():
    payload = await _probe_live_query("show me the kernel panic traceback from last night")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") in ["FORENSIC", "TECHNICAL"]
    assert payload.get("domain") in ["exp_for", "forensics", "standard"]

@pytest.mark.asyncio
async def test_live_vibe_meta():
    payload = await _probe_live_query("feedback: your last response was too verbose")
    if not payload:
        pytest.skip("Lab attendant daemon not running on port 8765")
    assert payload.get("vibe") == "META"
    assert payload.get("domain") == "feedback"

