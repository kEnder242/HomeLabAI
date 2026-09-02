import pytest
from unittest.mock import MagicMock, AsyncMock
from memory.blackboard_ledger import BlackboardLedger, ContextScope
from logic.cognitive_hub import CognitiveHub

def test_blackboard_ledger():
    ledger = BlackboardLedger()
    
    # Test record_bullet
    ledger.record_bullet(1, "Alice", "First bullet")
    ledger.record_bullet(1, "Bob", "Second bullet")
    
    # Test record_consensus
    ledger.record_consensus(1, "Consensus line 1")
    ledger.record_consensus(1, "Consensus line 2")
    
    # Test get_summary for specific turn
    summary = ledger.get_summary(1)
    assert "Distillation Bullets:" in summary
    assert "- [ALICE]: First bullet" in summary
    assert "- [BOB]: Second bullet" in summary
    assert "Consensus:" in summary
    assert "Consensus line 1" in summary
    assert "Consensus line 2" in summary
    
    # Test get_summary without turn filter
    ledger.record_bullet(2, "Charlie", "Third bullet")
    ledger.record_consensus(2, "Consensus line 3")
    summary_all = ledger.get_summary()
    assert "Distillation Bullets:" in summary_all
    assert "- [ALICE]: First bullet" in summary_all
    assert "- [BOB]: Second bullet" in summary_all
    assert "- [CHARLIE]: Third bullet" in summary_all
    assert "Consensus:" in summary_all
    assert "Consensus line 1" in summary_all
    assert "Consensus line 2" in summary_all
    assert "Consensus line 3" in summary_all

    # Test to_dict
    d = ledger.to_dict()
    assert d["count_bullets"] == 3
    assert d["count_consensus"] == 3

def test_context_scope():
    assert ContextScope.TURN.value == "TURN"
    assert ContextScope.LONG.value == "LONG"

@pytest.mark.asyncio
async def test_cognitive_hub_context_scoping():
    hub = CognitiveHub(residents={}, broadcast_callback=AsyncMock(), sensory_manager=None, get_vram_status=None, trigger_morning_briefing=None)
    hub.residents = {"triage": MagicMock(), "pinky": MagicMock()}
    hub.round_table_memory = ["User: Hello", "Pinky: Hi"]
    hub.blackboard_ledger.record_bullet(1, "pinky", "User greeted us")
    hub.blackboard_ledger.record_consensus(1, "Acknowledge greeting")

    # Mock resident call_tool to capture the transformed query
    captured_queries = []
    async def mock_call_tool(tool_name, arguments):
        captured_queries.append(arguments.get("query", ""))
        return "response chunk"

    hub.residents["triage"].call_tool = mock_call_tool
    hub.residents["pinky"].call_tool = mock_call_tool

    # 1. Triage query (should be TURN isolated: no previous debate, no blackboard)
    async for _ in hub._process_node_stream(
        node_id="triage",
        query="Classify intent",
        context="",
        source_name="TriageRelay",
        scope=ContextScope.TURN
    ):
        pass
    assert len(captured_queries) == 1
    assert "[PREVIOUS_DEBATE]" not in captured_queries[0]
    assert "[BLACKBOARD_LEDGER]" not in captured_queries[0]

    # 2. Pinky query (should be LONG enriched: contains blackboard ledger)
    async for _ in hub._process_node_stream(
        node_id="pinky",
        query="Evaluate response",
        context="",
        source_name="PinkyNode",
        scope=ContextScope.LONG
    ):
        pass
    assert len(captured_queries) == 2
    assert "[BLACKBOARD_LEDGER]" in captured_queries[1]
    assert "User greeted us" in captured_queries[1]
