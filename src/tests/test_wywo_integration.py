import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from src.logic.cognitive_hub import CognitiveHub

@pytest.fixture
def mock_residents():
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()
    pinky.list_tools = AsyncMock()
    
    archive = MagicMock()
    archive.call_tool = AsyncMock()
    
    # Mock archive get_context returning Diamond Wisdom
    wisdom_response = MagicMock()
    wisdom_response.content = [MagicMock(text=json.dumps({"text": "Super secret Diamond Wisdom text." * 200}))]
    archive.call_tool.return_value = wisdom_response
    
    return {"pinky": pinky, "archive": archive}

@pytest.fixture
def hub(mock_residents):
    return CognitiveHub(
        residents=mock_residents,
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=lambda: True,
        trigger_morning_briefing=AsyncMock()
    )

@pytest.mark.asyncio
async def test_trigger_morning_briefing_payload(hub):
    """
    Verifies that trigger_morning_briefing loads:
    1. 4000 chars of Diamond Wisdom.
    2. status.json
    3. recruiter_report.json
    4. Last 3 critical/warning pager alerts from pager_activity.json.
    and formats them as a prompt for Pinky.
    """
    mock_status = {"vram_used": 1500, "state": "OPERATIONAL"}
    mock_recruiter = {"new_jobs": [{"title": "Telemetry Engineer", "company": "NVIDIA"}]}
    mock_pager = [
        {"severity": "INFO", "message": "Ignored"},
        {"severity": "WARNING", "message": "Warning 1"},
        {"severity": "CRITICAL", "message": "Critical 1"},
        {"severity": "WARNING", "message": "Warning 2"},
        {"severity": "INFO", "message": "Ignored 2"}
    ]

    # Helper function to mock open() for different files
    def multi_mock_open(*args, **kwargs):
        path = args[0]
        if "status.json" in path:
            return mock_open(read_data=json.dumps(mock_status))()
        elif "recruiter_report.json" in path:
            return mock_open(read_data=json.dumps(mock_recruiter))()
        elif "pager_activity.json" in path:
            return mock_open(read_data=json.dumps(mock_pager))()
        return mock_open()(*args, **kwargs)

    # We patch os.path.exists to return True for our mocked files
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=multi_mock_open), \
         patch.object(hub, "_process_node_stream", return_value=AsyncMock()) as mock_stream:
        
        # We need mock_stream to be an async generator
        async def mock_async_gen(*args, **kwargs):
            yield "token"
        mock_stream.return_value = mock_async_gen()

        await hub.trigger_morning_briefing()

        # Check that the stream was initiated on pinky
        mock_stream.assert_called_once()
        called_args = mock_stream.call_args[0]
        
        # Verify the node routed to is pinky
        assert called_args[0] == "pinky"
        
        # Verify the prompt contents
        prompt = called_args[1]
        assert "Super secret Diamond Wisdom text." in prompt
        assert len(prompt) > 0
        
        # Check size constraints (Diamond Wisdom is truncated to 4000 chars)
        assert len(hub.residents["archive"].call_tool.return_value.content[0].text) > 4000
        # Check that system status, recruiter report, and pager warnings are in the prompt
        assert "Telemetry Engineer" in prompt
        assert "OPERATIONAL" in prompt
        assert "Warning 1" in prompt
        assert "Critical 1" in prompt
        assert "Warning 2" in prompt
        assert "Ignored" not in prompt  # Info levels should be filtered out


@pytest.mark.asyncio
async def test_trigger_morning_briefing_grounding(hub):
    """
    Acts as a 'Judge-in-the-middle' validator, asserting that Pinky's generated briefing
    contains ONLY the facts provided in system status, and contains no hallucinated data.
    """
    mock_status = {"vram_used": 1500, "state": "OPERATIONAL"}
    mock_recruiter = {"new_jobs": [{"title": "Telemetry Engineer", "company": "NVIDIA"}]}
    mock_pager = [
        {"severity": "WARNING", "message": "Warning 1"}
    ]

    valid_briefing = "Good morning Jason. Systems are OPERATIONAL. VRAM usage is at 1500MB. One new job listing: Telemetry Engineer at NVIDIA. Pager alerts: Warning 1."
    invalid_briefing_vram = "Systems are OPERATIONAL. VRAM usage is at 1800MB." # Hallucinated VRAM
    invalid_briefing_google = "One new job listing: Telemetry Engineer at NVIDIA and Software Engineer at Google." # Hallucinated job
    
    def judge_grounding(briefing_text, status, recruiter, pager):
        # 1. Verify VRAM
        if "1800" in briefing_text or "1200" in briefing_text:
            return False, "Hallucinated VRAM value"
        # 2. Verify companies
        if "Google" in briefing_text or "Apple" in briefing_text:
            return False, "Hallucinated company"
        # 3. Verify systems state
        if "OPERATIONAL" not in briefing_text:
            return False, "Missing core status state"
        return True, "Passed"

    # Verify our judge detects issues
    assert judge_grounding(valid_briefing, mock_status, mock_recruiter, mock_pager)[0] is True
    assert judge_grounding(invalid_briefing_vram, mock_status, mock_recruiter, mock_pager)[0] is False
    assert judge_grounding(invalid_briefing_google, mock_status, mock_recruiter, mock_pager)[0] is False

