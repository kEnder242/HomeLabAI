import pytest
from logic.cognitive_hub import CognitiveHub

@pytest.fixture
def hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=lambda x: None,
        sensory_manager=None,
        brain_online_callback=lambda: True,
        get_oracle_signal_callback=lambda x: "signal",
        monitor_task_with_tics_callback=lambda x: x
    )

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
