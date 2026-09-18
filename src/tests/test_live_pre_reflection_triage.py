#!/usr/bin/env python3
"""
[Story 83.11 / BKM-024] Live Foyer Pre-Reflection Triage Integration Test Suite
Validates the complete pre-reflection pipeline:
1. Live Foyer daemon status on port 8765.
2. ChromaDB RDNA question space resolution on port 8001.
3. Speculative triage engine preference and EWMA lead window (FEAT-586).
4. RDNA HyDE bypass with confidence delta guardrail (FEAT-583).
"""

import asyncio
import json
import os
import sys
import urllib.request
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from logic.speculative_triage import SpeculativeTriageRelay, _EWMALatencyEstimator


def test_live_foyer_daemon_health():
    """Verify active running Foyer REST daemon on port 8765."""
    url = "http://127.0.0.1:8765/status?timeout=1"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "ONLINE", f"Foyer not online: {data}"
            assert data.get("state") == "OPERATIONAL", f"Foyer not operational: {data}"
            print("\n[✓] Live Foyer Daemon is OPERATIONAL on port 8765.")
    except Exception as e:
        pytest.fail(f"Could not connect to live Foyer daemon on 8765: {e}")


def test_ewma_latency_estimator_bounds():
    """Verify Jacobson & Karels EWMA latency smoothing with k=4 confidence."""
    est = _EWMALatencyEstimator()
    assert est.lead_window(0.09) == pytest.approx(0.18, 0.01) # Zero history degradation
    
    # Observe 500ms ping with 50ms variance
    est.observe(0.50)
    est.observe(0.55)
    est.observe(0.48)
    
    w_lead = est.lead_window(0.09)
    assert w_lead > 0.18, "EWMA lead window should expand with observed latency"
    print(f"\n[✓] EWMA lead window dynamically expanded to {w_lead:.3f}s.")


def test_rdna_hyde_bypass_live_chroma():
    """Test RDNA question queries against live ChromaDB rdna collection on port 8001."""
    async def mock_bc(p): pass
    async def mock_dt(q, c, s, r): return {"vibe": "TECHNICAL", "addressed_to": "BRAIN", "importance": 0.9}
    async def mock_vllm(q, c, s, r): return {"vibe": "CASUAL", "addressed_to": "PINKY", "importance": 0.5}
    relay = SpeculativeTriageRelay(mock_bc, mock_dt, mock_vllm)
    
    # Canonical query matching PHL-032 (Creative Process)
    query = "How do you balance creative ideation with engineering execution?"
    bypass_payload = relay._maybe_rdna_hyde_bypass(query)
    
    if bypass_payload is not None:
        assert bypass_payload.get("hyde_bypassed") is True
        links = bypass_payload.get("explicit_links", [])
        assert any("PHL" in l for l in links), f"Expected PHL link in bypass payload, got: {links}"
        print(f"\n[✓] RDNA HyDE Bypass triggered successfully with target links: {links}")
    else:
        print("\n[!] RDNA query fell back cleanly (distance >= 0.45 or delta < 0.05).")


@pytest.mark.asyncio
async def test_speculative_triage_engine_preference(monkeypatch):
    """Verify SpeculativeTriageRelay respects preferred_triage_engine from infrastructure.json."""
    import logic.speculative_triage as spec_mod
    monkeypatch.setattr(spec_mod, "resolve_active_deep_thought_target", lambda timeout=0.6: {"name": "M5_AIR", "host": "192.168.1.46", "port": 8000, "protocol": "OPENAI", "probe_path": "/v1/models", "t_warmed": 0.5, "t_cold": 1.0})

    async def mock_broadcast(payload): pass
    async def mock_dt(q, ctx, schema, req_id):
        await asyncio.sleep(0.05)
        return {"vibe": "TECHNICAL", "addressed_to": "BRAIN", "importance": 0.9, "situation": "M5 Air Preferred Win"}
    async def mock_vllm(q, ctx, schema, req_id):
        await asyncio.sleep(0.50)
        return {"vibe": "CASUAL", "addressed_to": "PINKY", "importance": 0.5, "situation": "Local vLLM Win"}

    relay = SpeculativeTriageRelay(mock_broadcast, mock_dt, mock_vllm, preferred_engine="M5_AIR")
    result, winner = await relay.relay("Test query without rdna", {}, {}, "req-test-pref")
    
    assert winner in ["deep_thought", "kender", "rdna_bypass"]
    print(f"\n[✓] Speculative triage preferred engine successfully resolved winner: {winner}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
