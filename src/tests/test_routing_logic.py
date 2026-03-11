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

def test_route_expert_domain(hub):
    # Telemetry
    assert hub._route_expert_domain("what is the rapl reading?") == "exp_tlm"
    assert hub._route_expert_domain("check silicon telemetry") == "exp_tlm"
    
    # Architecture / BKM
    assert hub._route_expert_domain("let's discuss the bkm for class 1 architecture") == "exp_bkm"
    assert hub._route_expert_domain("architectural review of the hub") == "exp_bkm"
    
    # Forensic / History
    assert hub._route_expert_domain("search the history for ESB2") == "exp_for"
    assert hub._route_expert_domain("find forensic evidence of the crash") == "exp_for"
    
    # Default
    assert hub._route_expert_domain("something else entirely") == "exp_for"
