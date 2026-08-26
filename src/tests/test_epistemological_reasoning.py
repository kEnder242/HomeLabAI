"""
[FEAT-485] Epistemological Archival Reasoning Test Suite & Prompt Iteration Harness

Validates that CognitiveHub correctly digests [ARCHIVAL_EVIDENCE] temporal scarcity
envelopes from the Archive Node and injects EPISTEMOLOGICAL_PROTOCOL into behavioral guidance.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.logic.cognitive_hub import CognitiveHub


class TestEpistemologicalReasoning:
    """Tests for Epistemological Reasoning Protocol in CognitiveHub."""

    def test_epistemological_guidance_injected_on_scarcity_evidence(self):
        """When RAG returns [ARCHIVAL_EVIDENCE], guidance must command deductive negative assertion."""
        residents = {"pinky": MagicMock(), "brain": MagicMock(), "thought": MagicMock()}
        hub = CognitiveHub(
            residents=residents,
            broadcast_callback=AsyncMock(),
            sensory_manager=MagicMock(),
            get_vram_status=MagicMock(return_value={"vram": "healthy"}),
            trigger_morning_briefing=AsyncMock()
        )

        scarcity_rag_context = (
            "[ARCHIVAL_EVIDENCE]:\n"
            "- Query Entity: 'Kayak'\n"
            "- Target Year Evaluated: 2008 (0 records found in 18-year archive)\n"
            "- Archival Timeline Distribution: Verified matches exist in years [2014, 2019]\n"
            "- Temporal Scarcity Diagnostic: Target entity was active in [2014, 2019], but confirmed ABSENT in target year 2008."
        )

        mock_triage_result = {
            "vibe": "HISTORICAL",
            "domain": "lab_history",
            "importance": 0.9,
            "intrigue": 0.85,
            "casual": 0.05,
            "addressed_to": "PINKY",
            "situation": "Temporal verification query",
            "hints": "2008 era"
        }

        captured_guidance = []

        async def run_test():
            with patch.object(hub.triage_relay, "relay", new=AsyncMock(return_value=(mock_triage_result, "kender"))), \
                 patch.object(hub, "_fetch_rag_context", new=AsyncMock(return_value=scarcity_rag_context)), \
                 patch.object(hub, "_process_node_stream") as mock_stream:

                async def intercept_stream(*args, **kwargs):
                    captured_guidance.append(kwargs.get("behavioral_guidance", ""))
                    yield "Test token"

                mock_stream.side_effect = intercept_stream
                await hub.process_query("was Kayak really in 2008?")

        asyncio.run(run_test())

        assert len(captured_guidance) > 0
        full_guidance = " ".join(captured_guidance)
        assert "EPISTEMOLOGICAL_PROTOCOL" in full_guidance
        assert "temporal scarcity" in full_guidance
        assert "NOT present/active" in full_guidance
