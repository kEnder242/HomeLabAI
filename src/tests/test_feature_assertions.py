import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from src.logic.cognitive_hub import CognitiveHub
from src.nodes.loader import BicameralNode


@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    pinky.list_tools = AsyncMock()
    pinky.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])

    lab = MagicMock()
    lab.call_tool = AsyncMock()
    lab.list_tools = AsyncMock()
    lab.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])

    brain = MagicMock()
    brain.call_tool = AsyncMock()
    brain.list_tools = AsyncMock()
    brain.list_tools.return_value = MagicMock(tools=[MagicMock(name="think")])

    thought = MagicMock()
    thought.call_tool = AsyncMock()
    thought.list_tools = AsyncMock()

    archive = MagicMock()
    archive.call_tool = AsyncMock()
    archive.list_tools = AsyncMock()

    return {
        "pinky": pinky, "lab": lab, "brain": brain,
        "thought": thought, "archive": archive
    }


@pytest.fixture
def hub(mock_residents):
    return CognitiveHub(
        residents=mock_residents,
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=lambda: True,
        trigger_morning_briefing=AsyncMock(),
        set_active_domain=MagicMock()
    )


@pytest.mark.asyncio
async def test_feat_404_context_starvation(hub):
    """
    FEAT-404: Context Starvation Detection & Mid-Stream Abort.
    Verifies that when a node response contains [ERROR: CONTEXT_STARVED],
    the node is tracked in context_starved_nodes and the error token
    is propagated through the stream.
    """
    hub.residents["lab"].call_tool.return_value = MagicMock(
        content=[MagicMock(text="[ERROR: CONTEXT_STARVED]")]
    )

    tokens = []
    async for token in hub._process_node_stream(
        "lab", "test query", "", "Lab",
        request_id="feat404_test"
    ):
        tokens.append(token)

    assert "lab" in hub.context_starved_nodes, \
        "lab node should be tracked in context_starved_nodes after starvation"
    assert len(tokens) > 0, "stream should yield tokens even on starvation"
    assert any("[ERROR: CONTEXT_STARVED]" in t for t in tokens), \
        "stream should propagate the [ERROR: CONTEXT_STARVED] token"


@pytest.mark.asyncio
async def test_feat_407_historical_record_isolation(hub):
    """
    FEAT-407: Historical Record Isolation via <historical_record> XML Wrapping.
    Verifies that when current_vibe is HISTORICAL (or FORENSIC/TECHNICAL),
    the RAG context is wrapped in <historical_record> XML tags and
    GROUNDING_PROTOCOL is injected into behavioral_guidance.
    """
    hub.current_vibe = "HISTORICAL"
    hub.residents["pinky"].call_tool.return_value = MagicMock(
        content=[MagicMock(text="mock historical response")]
    )

    tokens = []
    async for token in hub._process_node_stream(
        "pinky", "query about 2019 events", "source context",
        "Pinky", request_id="feat407_test"
    ):
        tokens.append(token)

    assert hub.residents["pinky"].call_tool.called, \
        "Pinky's call_tool should have been invoked"

    # The arguments dict is passed as a keyword argument named 'arguments'
    call_args = hub.residents["pinky"].call_tool.call_args
    params = call_args[1]["arguments"]

    context_arg = params.get("context", "")
    guidance_arg = params.get("behavioral_guidance", "")

    assert "<historical_record>" in context_arg, \
        "context should be wrapped in opening <historical_record> tag"
    assert "source context" in context_arg, \
        "original context content should be preserved inside the tags"
    assert "</historical_record>" in context_arg, \
        "context should be wrapped in closing </historical_record> tag"
    assert "GROUNDING_PROTOCOL" in guidance_arg, \
        "GROUNDING_PROTOCOL should be appended to behavioral_guidance"
    assert len(tokens) > 0, "stream should yield response tokens"


@pytest.mark.asyncio
async def test_feat_409_wywo_vibe_routing(hub):
    """
    FEAT-409: WYWO Vibe Routing & Context Loading.
    Verifies that a status query is triaged to WYWO vibe, which loads
    nightly_dialogue.json for [NIGHTLY_DIALOGUE_RECORD] and fetches
    Diamond Wisdom for [SUBCONSCIOUS_DREAM_WISDOM] as context, and
    sets behavioral_guidance to [MODE]: STANDUP.
    """
    wywo_triage = json.dumps({
        "addressed_to": "PINKY", "vibe": "WYWO", "domain": "standard",
        "casual": 0.5, "intrigue": 0.3, "importance": 0.3,
        "situation": "status check", "hints": ""
    })
    hub.residents["lab"].call_tool.return_value = MagicMock(
        content=[MagicMock(text=wywo_triage)]
    )
    hub.residents["pinky"].call_tool.return_value = MagicMock(
        content=[MagicMock(text="Here is the nightly summary.")]
    )

    # Mock archive.get_context to return Diamond Wisdom
    mock_wisdom = MagicMock()
    mock_wisdom.content = [MagicMock(text="Diamond Wisdom: thermal analysis results.")]
    hub.residents["archive"].call_tool.return_value = mock_wisdom

    # Mock nightly_dialogue.json
    mock_nightly = {
        "topic": "Overnight Thermal Analysis",
        "content": "The nodes discussed GPU thermal throttling patterns."
    }

    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(mock_nightly))):
        await hub.process_query("What happened last night?")

    # Verify Pinky received WYWO context
    assert hub.residents["pinky"].call_tool.called, \
        "Pinky's call_tool should have been invoked for WYWO response"

    call_args = hub.residents["pinky"].call_tool.call_args
    params = call_args[1]["arguments"]

    context_arg = params.get("context", "")
    guidance_arg = params.get("behavioral_guidance", "")

    assert "[NIGHTLY_DIALOGUE_RECORD]" in context_arg, \
        "WYWO context should contain nightly dialogue record header"
    assert "[SUBCONSCIOUS_DREAM_WISDOM]" in context_arg, \
        "WYWO context should contain subconscious dream wisdom header"
    assert "Overnight Thermal Analysis" in context_arg, \
        "nightly dialogue topic should appear in WYWO context"
    assert "thermal throttling" in context_arg, \
        "nightly dialogue content should appear in WYWO context"
    assert "[MODE]: STANDUP" in guidance_arg, \
        "WYWO routing should set behavioral_guidance to STANDUP mode"
    assert "Diamond Wisdom" in context_arg, \
        "Diamond Wisdom should be included in WYWO context"


def test_feat_411_append_to_tool_log(tmp_path):
    """
    FEAT-411: Structured Tool Execution Logging.
    Verifies that append_to_tool_log appends a correctly formatted entry
    with timestamp, node name, tool name, and params preview to tool_log.md.
    """
    log_path = tmp_path / "tool_log.md"

    with patch("src.nodes.loader.TOOL_LOG_PATH", str(log_path)):
        node = BicameralNode("TestNode", "test prompt")
        node.append_to_tool_log("think", 'query="hello"')

        assert log_path.exists(), "tool_log.md should be created"

        content = log_path.read_text()
        assert "[testnode]" in content, \
            "log entry should contain the lowercased node name"
        assert "think" in content, \
            "log entry should contain the tool name"
        assert 'query="hello"' in content, \
            "log entry should contain the params preview"
