import pytest
from HomeLabAI.src.cognitive_hub import CognitiveHub

def test_reset_flow():
    hub = CognitiveHub()
    # Simulate sending '/topic' reset signal
    hub.process_signal('/topic reset')
    # Assert context is cleared
    assert hub.context == {}, "Context was not cleared after reset signal"

if __name__ == "__main__":
    pytest.main()