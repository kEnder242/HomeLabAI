"""
[FEAT-636] In-Flight Dynamic Retrieval Scope Override ("Direct Flight") Unit Tests
Sprint: SPR-96.0 (Story 96.4)
"""

import json
import pytest
from nodes.brain_node import direct_flight_override


@pytest.mark.asyncio
async def test_direct_flight_override_execution():
    """Verify direct_flight_override queries targeted collection without re-triage."""
    res_str = await direct_flight_override(
        target_domain="behavioral_dna", query="BKM-060 Federated DNA taxonomy"
    )
    res = json.loads(res_str)
    assert "min_distance" in res
    assert "results_by_collection" in res
    assert "behavioral_dna" in res["results_by_collection"]
    # Ensure unrequested domains were not queried
    assert "career_ledger" not in res["results_by_collection"]


@pytest.mark.asyncio
async def test_direct_flight_override_zero_dna():
    """Verify direct_flight_override handles zero-DNA gracefully."""
    res_str = await direct_flight_override(target_domain="", query="hello")
    res = json.loads(res_str)
    assert "min_distance" in res
    assert "results_by_collection" in res
