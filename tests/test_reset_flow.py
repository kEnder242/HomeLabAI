# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
import pytest

from HomeLabAI.src.cognitive_hub import CognitiveHub


def test_reset_flow():
    hub = CognitiveHub()
    # Simulate sending '/topic' reset signal
    hub.process_signal("/topic reset")
    # Assert context is cleared
    assert hub.context == {}, "Context was not cleared after reset signal"


if __name__ == "__main__":
    pytest.main()
