"""
[FEAT-636] Direct Flight: In-Flight Dynamic Retrieval Scope Override Unit Tests
Sprint: SPR-96.0 (Story 96.4)
"""
import json

import pytest
from unittest.mock import patch

from nodes.brain_node import direct_flight_override


@pytest.mark.asyncio
async def test_direct_flight_override_success():
    mock_res = {
        "semantic_hint": "[HINT: Blackboard]",
        "best_doc": "Prior turn context",
        "min_distance": 0.25,
    }
    with patch("logic.vector_pre_triage.probe_clara_dna_sync", return_value=mock_res):
        raw = await direct_flight_override(target_domains=["blackboard_ledger_dna"], query="earlier discussion")
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["target_domains"] == ["blackboard_ledger_dna"]
        assert data["best_doc"] == "Prior turn context"


@pytest.mark.asyncio
async def test_direct_flight_override_error_handling():
    with patch("logic.vector_pre_triage.probe_clara_dna_sync", side_effect=RuntimeError("Chroma down")):
        raw = await direct_flight_override(target_domains=["behavioral_dna"], query="test")
        data = json.loads(raw)
        assert data["status"] == "error"
        assert "Chroma down" in data["message"]