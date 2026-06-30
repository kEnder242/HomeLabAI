import pytest
from logic.cognitive_hub import CognitiveHub

@pytest.fixture
def hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=lambda x: None,
        sensory_manager=None,
        get_vram_status=lambda: {"total": 11000, "free": 8000},
        trigger_morning_briefing=lambda: None
    )

@pytest.mark.skip(reason="Legacy V4 local router replaced by V5 Lab Triage Node")
@pytest.mark.asyncio
async def test_route_expert_domain(hub):
    # Telemetry
    route = await hub._route_expert_domain("what is the rapl reading?")
    assert route in ["exp_tlm", "exp_for"]
    
    # Architecture / BKM
    route = await hub._route_expert_domain("let's discuss the bkm for class 1 architecture")
    assert route in ["exp_bkm", "exp_for"]
    
    # Forensic / History
    route = await hub._route_expert_domain("search the history for ESB2")
    assert route == "exp_for"
    
    # Default
    route = await hub._route_expert_domain("something else entirely")
    assert route == "exp_for"
