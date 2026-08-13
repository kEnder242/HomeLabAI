"""
[FEAT-437] 3-Tier HyDE Failover Cascade test suite.

Verifies resolve_hyde_vector() tier resolution:
  1. Tier 1 hit (DEEP_THOUGHT_REMOTE): Kender 4090 thought node returns HyDE.
  2. Tier 2 (PINKY_LOCAL_VLLM): Kender timeout / exception -> triage hyde_vector_text.
  3. Tier 3 (DIRECT_RAW_QUERY): both offline / empty -> raw query passthrough.
Plus integration: the resolved HyDE flows into archive get_context.
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from logic.cognitive_hub import (
    CognitiveHub,
    HYDE_SYNTHESIS_PROMPT,
    DEEP_THOUGHT_REMOTE,
    PINKY_LOCAL_VLLM,
    DIRECT_RAW_QUERY,
)

TIER1_TEXT = "[VALIDATION]: AEP | [STRATEGY]: goal | [SRE]: cmd"


def _make_hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=None,
        sensory_manager=None,
        get_vram_status=None,
        trigger_morning_briefing=None,
    )


def _thought_mock(return_value=None, side_effect=None):
    thought = MagicMock()
    thought.call_tool = AsyncMock(return_value=return_value, side_effect=side_effect)
    return thought


@pytest.mark.asyncio
async def test_tier1_deep_thought_hit():
    """Tier 1: Kender thought node returns a HyDE vector -> DEEP_THOUGHT_REMOTE."""
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(
        return_value=MagicMock(content=[MagicMock(text=TIER1_TEXT)])
    )
    vec, tier = await hub.resolve_hyde_vector("query", {})
    assert tier == DEEP_THOUGHT_REMOTE
    assert vec == TIER1_TEXT
    hub.residents["thought"].call_tool.assert_awaited_once_with(
        "deep_think", {"task": HYDE_SYNTHESIS_PROMPT, "context": "query"}
    )


@pytest.mark.asyncio
async def test_tier1_timeout_falls_to_tier2():
    """Tier 2: Kender times out -> triage hyde_vector_text used."""
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(side_effect=asyncio.TimeoutError())
    vec, tier = await hub.resolve_hyde_vector("query", {"hyde_vector_text": "Narf! local triage hyde"})
    assert tier == PINKY_LOCAL_VLLM
    assert vec == "Narf! local triage hyde"


@pytest.mark.asyncio
async def test_tier1_exception_falls_to_tier2():
    """Tier 2: Kender call raises (offline) -> triage hyde_vector_text used."""
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(side_effect=ConnectionError("kender down"))
    vec, tier = await hub.resolve_hyde_vector("query", {"hyde_vector_text": "Narf! local triage hyde"})
    assert tier == PINKY_LOCAL_VLLM
    assert vec == "Narf! local triage hyde"


@pytest.mark.asyncio
async def test_tier3_raw_query_fallback():
    """Tier 3: no thought node, empty triage -> raw query passthrough, no crash."""
    hub = _make_hub()
    vec, tier = await hub.resolve_hyde_vector("raw query", {})
    assert tier == DIRECT_RAW_QUERY
    assert vec == "raw query"


@pytest.mark.asyncio
async def test_tier2_short_hyde_falls_to_tier3():
    """Length gate (>10 chars): short triage hyde does not satisfy Tier 2."""
    hub = _make_hub()
    vec, tier = await hub.resolve_hyde_vector("query", {"hyde_vector_text": "short"})
    assert tier == DIRECT_RAW_QUERY
    assert vec == "query"


@pytest.mark.asyncio
async def test_tier1_empty_response_falls_to_tier3():
    """Kender returns empty text -> skipped; empty triage -> Tier 3."""
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(
        return_value=MagicMock(content=[MagicMock(text="   ")])
    )
    vec, tier = await hub.resolve_hyde_vector("query", {})
    assert tier == DIRECT_RAW_QUERY
    assert vec == "query"


@pytest.mark.asyncio
async def test_fetch_rag_context_tier1_flows_to_get_context():
    """Integration: Tier 1 HyDE is what archive get_context receives."""
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(
        return_value=MagicMock(content=[MagicMock(text=TIER1_TEXT)])
    )
    archive = MagicMock()
    archive.call_tool = AsyncMock(return_value=MagicMock(content=[MagicMock(text="ctx")]))
    hub.residents["archive"] = archive

    result = await hub._fetch_rag_context("query", {})
    assert result == "ctx"
    archive.call_tool.assert_awaited_once_with(
        "get_context", {"query": "query", "hyde_vector_text": TIER1_TEXT, "n_results": 3}
    )


@pytest.mark.asyncio
async def test_tier1_log_emitted(caplog):
    """Server log contract: [FEAT-437][TIER1] on Kender hit."""
    caplog.set_level(logging.INFO)
    hub = _make_hub()
    hub.residents["thought"] = _thought_mock(
        return_value=MagicMock(content=[MagicMock(text=TIER1_TEXT)])
    )
    await hub.resolve_hyde_vector("query", {})
    assert "[FEAT-437][TIER1]" in caplog.text


@pytest.mark.asyncio
async def test_tier3_log_emitted(caplog):
    """Server log contract: [FEAT-437][TIER3] on raw passthrough."""
    caplog.set_level(logging.INFO)
    hub = _make_hub()
    await hub.resolve_hyde_vector("raw query", {})
    assert "[FEAT-437][TIER3]" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])