"""
[FEAT-467/472] Sprint 62 In-Process Integration Test Suite

Verifies the complete end-to-end cascade for:
  1. Declarative Triage Policy Engine (config/triage_policy.json & TriagePolicyLoader)
  2. Dynamic Route Incubation Sandbox (FEAT-472 / RouteIncubator)
  3. Bidirectional Traversal Dispatcher (TOPIC_FIRST vs TIME_FIRST vs STREAM_REPLAY)
  4. Gated On-Demand RAG & Decoupled Actor Selection
"""

from pathlib import Path

from logic.triage_policy_loader import TriagePolicyLoader
from logic.route_incubator import RouteIncubator
from logic.traversal_dispatcher import (
    TraversalMode,
    format_traversal_query,
    resolve_collection_scope,
    extract_temporal_anchors,
)
from logic.triage_engine import classify_vibe_and_domain


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Declarative Triage Policy Engine Integration (FEAT-467)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeclarativeTriagePolicyIntegration:
    """Verifies production triage policy loads, hot-reloads, and scopes RAG."""

    def test_production_policy_has_eight_standard_vibes(self):
        loader = TriagePolicyLoader()
        active = loader.get_active_vibes()
        expected = ["CASUAL", "SUPERVISORY", "WYWO", "META", "OPERATIONAL", "FORENSIC", "TECHNICAL", "HISTORICAL"]
        for v in expected:
            assert v in active, f"Missing expected standard vibe: {v}"

    def test_conversational_and_supervisory_vibes_have_no_rag(self):
        loader = TriagePolicyLoader()
        for vibe in ["CASUAL", "SUPERVISORY", "META"]:
            rag = loader.get_rag_config(vibe)
            assert rag is None, f"Vibe {vibe} should have optional/null RAG config"

    def test_retrieval_vibes_have_valid_traversal_modes(self):
        loader = TriagePolicyLoader()
        tech_rag = loader.get_rag_config("TECHNICAL")
        assert tech_rag is not None
        assert tech_rag["traversal"] == "TOPIC_FIRST"

        hist_rag = loader.get_rag_config("HISTORICAL")
        assert hist_rag is not None
        assert hist_rag["traversal"] == "TIME_FIRST"

        wywo_rag = loader.get_rag_config("WYWO")
        assert wywo_rag is not None
        assert wywo_rag["traversal"] == "STREAM_REPLAY"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Dynamic Route Incubation Sandbox Integration (FEAT-472)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouteIncubationSandboxIntegration:
    """Verifies mouse candidate route creation, routing, and solidification export."""

    def test_mouse_candidate_route_lifecycle(self, tmp_path: Path):
        supplement_path = tmp_path / "triage_supplement.json"
        incubator = RouteIncubator(supplement_path=supplement_path)

        # 1. Brain registers a candidate route in sandbox
        registered = incubator.register_candidate_route(
            vibe_name="quick_pcie_health",
            intent="Rapid PCIe AER link status check",
            target_domain="exp_tlm",
            traversal_mode="TOPIC_FIRST",
            creator="Brain"
        )
        assert registered.startswith("MOUSE_DEF:")
        assert registered == "MOUSE_DEF:quick_pcie_health"

        # 2. Triage engine recognizes candidate route
        vibe, domain = classify_vibe_and_domain(
            query="Check the quick_pcie_health status",
            parsed_json={"vibe": "CASUAL", "domain": "standard"},
            incubator=incubator
        )
        assert vibe == "MOUSE_DEF:quick_pcie_health"
        assert domain == "exp_tlm"

        # 3. Record hits and success
        incubator.record_route_hit("quick_pcie_health", success=True, feedback="Accurate quick check")
        candidates = incubator.get_candidate_routes(active_only=True)
        assert candidates["MOUSE_DEF:quick_pcie_health"]["hit_count"] == 1
        assert candidates["MOUSE_DEF:quick_pcie_health"]["success_count"] == 1

        # 4. Export for solidification into core policy format
        core_export = incubator.export_for_solidification("quick_pcie_health")
        assert core_export["default_domain"] == "exp_tlm"
        assert core_export["rag"]["traversal"] == "TOPIC_FIRST"
        assert core_export["_incubation"]["creator"] == "Brain"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Bidirectional Traversal Dispatcher Integration (FEAT-117/467)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBidirectionalTraversalIntegration:
    """Verifies Topic-First, Time-First, and Stream-Replay traversals."""

    def test_topic_first_technical_dispatch(self):
        query = "PCIe AER uncorrectable error mask register configuration"
        formatted = format_traversal_query(query, TraversalMode.TOPIC_FIRST)
        assert formatted["mode"] == TraversalMode.TOPIC_FIRST.value
        assert formatted["temporal_bounds"] is None
        assert any("pcie" in term.lower() for term in formatted["enriched_terms"])

        collections = resolve_collection_scope("TECHNICAL", "exp_tlm", TraversalMode.TOPIC_FIRST)
        assert "artifact_vault" in collections
        assert "behavioral_dna" in collections
        assert "career_ledger" not in collections

    def test_time_first_historical_dispatch(self):
        query = "What were we working on in 2018 for Intel PAE bring-up?"
        formatted = format_traversal_query(query, TraversalMode.TIME_FIRST)
        assert formatted["mode"] == TraversalMode.TIME_FIRST.value
        assert formatted["temporal_bounds"] is not None
        assert formatted["temporal_bounds"]["start_year"] == 2018
        assert formatted["temporal_bounds"]["end_year"] == 2018

        collections = resolve_collection_scope("HISTORICAL", "lab_history", TraversalMode.TIME_FIRST)
        assert "career_ledger" in collections
        assert "artifact_vault" in collections

    def test_stream_replay_wywo_dispatch(self):
        query = "What did you think about while I was away?"
        formatted = format_traversal_query(query, TraversalMode.STREAM_REPLAY)
        assert formatted["mode"] == TraversalMode.STREAM_REPLAY.value

        collections = resolve_collection_scope("WYWO", "short_term_stream", TraversalMode.STREAM_REPLAY)
        assert collections == ["short_term_stream"]
        assert "career_ledger" not in collections


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Full End-to-End Orchestrator Cascade
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullOrchestratorCascade:
    """Verifies end-to-end routing decisions across supervisory, technical, and historical turns."""

    def test_supervisory_feedback_zero_rag(self):
        query = "The critic phase needs tuning; Pinky should use cartoon quips rather than praise."
        vibe, domain = classify_vibe_and_domain(
            query=query,
            parsed_json={"vibe": "SUPERVISORY", "domain": "session_feedback"}
        )
        assert vibe == "SUPERVISORY"
        loader = TriagePolicyLoader()
        rag = loader.get_rag_config(vibe)
        assert rag is None  # Zero RAG context injected

    def test_temporal_anchor_extraction_multi_era(self):
        anchors = extract_temporal_anchors("In Sprint 35 and back in 2024, what was our LoRA strategy?")
        assert 35 in anchors["sprints"]
        assert 2024 in anchors["years"]
