"""Unit test verifying Story 101.2: Residual Dialogue Abort Event Clearing."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from logic.cognitive_hub import CognitiveHub


@pytest.mark.asyncio
async def test_cognitive_hub_abort_reset():
    # Setup minimal mocks for CognitiveHub constructor
    residents = {}
    broadcast_cb = AsyncMock()
    sensory = MagicMock()
    get_vram = MagicMock(return_value=True)
    trigger_morning = MagicMock()

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=broadcast_cb,
        sensory_manager=sensory,
        get_vram_status=get_vram,
        trigger_morning_briefing=trigger_morning,
    )

    # Invariant 1: Fresh instance starts with turn_aborted = False
    assert hub.turn_aborted is False

    # Invariant 2: Aborting turn sets turn_aborted = True
    hub.abort_current_turn()
    assert hub.turn_aborted is True

    # Invariant 3: Calling process_query resets turn_aborted to False
    hub.request_lock = asyncio.Lock()
    hub.processed_ids = []
    
    # Process a basic trigger task which returns immediately
    await hub.process_query("[TRIGGER] test_noop")
    assert hub.turn_aborted is False
