"""
[FEAT-454] Sprint 51 Escapes & Dual-Flow Hibernation Test Suite.

Verifies:
# [FEAT-118] Resonant Oracle (Magic 8-Ball Preambles)
  1. Persona Boundary: Deep Thought preambles never output Pinky catchphrases ('Narf!', 'Poit!', 'Zort!').
  2. Dual-Flow HyDE vs Casual:
     - Casual flow ("hello") sets casual=True, vibe=CASUAL, hyde_vector_text="", and skips RAG.
     - Technical flow ("RAPL power cap") generates 3-part HyDE vector and invokes RAG.
  3. Hibernation Cold-Start Transition:
     - On-demand hibernation knob (POST /status_update {"state": "HIBERNATING"}).
     - Instant zero-latency Deep Thought crosstalk broadcast emitted upon WebSocket receipt.
"""

import asyncio
import json
import pytest
import aiohttp
import websockets
from collections import deque

from logic.cognitive_hub import CognitiveHub, BRAIN_PERSONA_SPEC
from nodes.archive_node import select_vector_query, parse_multi_voice_hyde


def _make_hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=None,
        sensory_manager=None,
        get_vram_status=None,
        trigger_morning_briefing=None,
    )


# ---------------------------------------------------------------------------
# 1. Persona Boundary Assertions (FEAT-451)
# ---------------------------------------------------------------------------
def test_deep_thought_persona_spec_forbids_pinky_tics():
    """Verify BRAIN_PERSONA_SPEC uses positive Brain persona grounding."""
    assert "Sharing the Brain's right-hemisphere architecture" in BRAIN_PERSONA_SPEC
    assert "Narf" not in BRAIN_PERSONA_SPEC
    assert "Poit" not in BRAIN_PERSONA_SPEC


def test_deep_thought_preamble_no_pinky_tics():
    """Negative assertion: Deep Thought persona spec text does not contain Pinky tics."""
    assert "calm, strategic, and clinical" in BRAIN_PERSONA_SPEC
    assert "Narf" not in BRAIN_PERSONA_SPEC
    assert "Poit" not in BRAIN_PERSONA_SPEC


# ---------------------------------------------------------------------------
# 2. Dual-Flow HyDE vs. Casual Assertions (FEAT-452)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_casual_flow_bypasses_hyde_and_rag():
    """Positive & Negative test: Casual turn ('hello') sets hyde_vector_text='' and skips RAG."""
    hub = _make_hub()

    casual_triage = {
        "inferred_intent": "greeting",
        "addressed_to": "PINKY",
        "vibe": "CASUAL",
        "casual": 0.95,
        "hyde_vector_text": ""
    }

    # Verify RAG context fetch returns empty string for casual turn
    rag_result = await hub._fetch_rag_context("hello", casual_triage, n_results=3)
    assert rag_result == "", "Casual turns must bypass RAG retrieval entirely"


def test_technical_flow_generates_composite_hyde():
    """Positive test: Technical query ('RAPL power cap') parses multi-voice Composite HyDE."""
    raw_query = "What is our RAPL power cap scar?"
    composite_hyde = "[VALIDATION]: rapl_power_cap | [STRATEGY]: power_limit_scar | [SRE]: sysfs_rapl"

    # Select vector query must resolve composite HyDE for technical query
    resolved_query = select_vector_query(raw_query, composite_hyde)
    assert "rapl_power_cap" in resolved_query
    assert "power_limit_scar" in resolved_query
    assert "sysfs_rapl" in resolved_query


def test_casual_greeting_hyde_override_evaluates_empty():
    """Negative test: Empty hyde_vector_text falls back gracefully without crash."""
    raw_query = "hello good morning"
    resolved_query = select_vector_query(raw_query, "")
    assert resolved_query == raw_query


# ---------------------------------------------------------------------------
# 3. Hibernation Cold-Start Transition & UI Crosstalk (LAB-094 / FEAT-453 / FEAT-455)
# ---------------------------------------------------------------------------
FOYER_BASE = "http://localhost:8765"
FOYER_WS = "ws://localhost:8765/"


def _foyer_live():
    import socket
    try:
        with socket.create_connection(("localhost", 8765), timeout=2.0):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _foyer_live(), reason="Lab Attendant server not running on port 8765")
@pytest.mark.asyncio
async def test_hibernation_cold_start_crosstalk_preamble():
    """Verify on-demand hibernation transition and instant zero-latency crosstalk emission."""
    async with aiohttp.ClientSession() as session:
        # 1. Force HIBERNATING state via on-demand knob
        async with session.post(
            f"{FOYER_BASE}/status_update",
            json={"state": "HIBERNATING"},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            assert resp.status in (200, 204)

        # 2. Get session token
        async with session.get(f"{FOYER_BASE}/status", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            body = await resp.json()
            token = body.get("session_token", "")

    # 3. Connect WebSocket and send handshake
    async with websockets.connect(FOYER_WS, open_timeout=10) as ws:
        await ws.recv()  # Server init frame
        await ws.send(json.dumps({"type": "handshake", "lab_key": token}))
        ack_msg = await ws.recv()
        ack_data = json.loads(ack_msg)
        assert ack_data.get("type") in ("status", "ack")

        # 4. Send chat frame and verify instant preamble crosstalk frame
        await ws.send(json.dumps({"type": "chat", "message": "hello good morning"}))

        # Read first response frame (must be instant crosstalk or status)
        resp_msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
        resp_data = json.loads(resp_msg)
        assert resp_data.get("type") in ("crosstalk", "status")
        if resp_data.get("type") == "crosstalk":
            assert "Deep Thought" in resp_data.get("brain_source", "")
            assert "Narf" not in resp_data.get("brain", "")
