"""
[FEAT-632 / FEAT-633 / FEAT-634] Unit Test Suite for Foyer Feedback Telemetry & Ledger Ingestion
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from v5.foyer.router import FoyerRouter


@pytest.mark.asyncio
async def test_handle_feedback_success(tmp_path, monkeypatch):
    test_ledger = str(tmp_path / "foyer_feedback_ledger.jsonl")
    
    # Mock expanduser to use temp file
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda p: test_ledger if "foyer_feedback_ledger.jsonl" in p else p,
    )
    
    # Create mock request with JSON payload
    req = AsyncMock(spec=web.Request)
    req.json.return_value = {
        "turn_id": "turn_test_123",
        "rating": "UP",
        "notes": "Excellent grounded retrieval",
    }
    
    # Mock FoyerRouter instance
    router = MagicMock(spec=FoyerRouter)
    router.handle_feedback = FoyerRouter.handle_feedback.__get__(router, FoyerRouter)
    
    res = await router.handle_feedback(req)
    assert res.status == 200
    
    body = json.loads(res.body.decode("utf-8"))
    assert body["status"] == "success"
    assert body["recorded"]["turn_id"] == "turn_test_123"
    assert body["recorded"]["rating"] == "UP"
    assert body["recorded"]["notes"] == "Excellent grounded retrieval"
    
    # Verify ledger file on disk
    assert os.path.exists(test_ledger)
    with open(test_ledger, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["turn_id"] == "turn_test_123"
    assert data["rating"] == "UP"


@pytest.mark.asyncio
async def test_handle_feedback_invalid_payload(monkeypatch):
    req = AsyncMock(spec=web.Request)
    req.json.side_effect = Exception("Malformed JSON")
    
    router = MagicMock(spec=FoyerRouter)
    router.handle_feedback = FoyerRouter.handle_feedback.__get__(router, FoyerRouter)
    
    res = await router.handle_feedback(req)
    assert res.status == 400
    body = json.loads(res.body.decode("utf-8"))
    assert body["status"] == "error"
