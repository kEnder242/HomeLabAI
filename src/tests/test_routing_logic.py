import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logic.cognitive_hub import CognitiveHub

@pytest.fixture
def hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=lambda x: None,
        sensory_manager=None,
        brain_online_callback=lambda: True,
        get_oracle_signal_callback=lambda x: "test",
        monitor_task_with_tics_callback=lambda x: x
    )

def test_route_expert_domain(hub):
    assert hub._route_expert_domain("what is the rapl reading?") == "exp_tlm"
    assert hub._route_expert_domain("let's discuss the bkm for class 1 architecture") == "exp_bkm"
    assert hub._route_expert_domain("search the archive for yesterday's issue") == "exp_for"
    assert hub._route_expert_domain("help me build my cvt for the recruiter") == "exp_rec"
    assert hub._route_expert_domain("hello pinky") == ""
