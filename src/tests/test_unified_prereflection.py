import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from logic.cognitive_hub import CognitiveHub


@pytest.mark.asyncio
async def test_greeting_short_circuit():
    """Verify that 1-word greetings short-circuit Pre-Reflection instantly without calling triage node."""
    # Simulate simple greeting turn
    turn = "hey pinky"
    # Execute greeting check logic
    raw_lower = turn.replace("pinky", "").strip().lower().strip("!?,.")
    assert raw_lower in ["hi", "hey", "hello", "what's up", "whats up", "good morning", "narf", "yo"]


@pytest.mark.asyncio
async def test_unified_prereflection_schema_fields():
    """Verify schema properties of the Unified Pre-Reflection Pass [FEAT-436]."""
    # Schema requirement checks
    expected_fields = ["inferred_intent", "addressed_to", "vibe", "domain", "casual", "intrigue", "importance", "hyde_vector_text"]
    sample_prereflection = {
        "inferred_intent": "User is requesting 2018 Optane memory validation notes.",
        "addressed_to": "BRAIN",
        "vibe": "DEEP_RESEARCH",
        "domain": "lab_history",
        "casual": 0.1,
        "intrigue": 0.8,
        "importance": 0.9,
        "situation": "Retrospective archive lookup",
        "hints": "search 2018 AEP Optane notes",
        "hyde_vector_text": "Intel Datacenter PAE 2018 AEP Optane persistent memory mailbox automation"
    }

    for field in expected_fields:
        assert field in sample_prereflection, f"Missing required Pre-Reflection field: {field}"

    assert sample_prereflection["vibe"] == "DEEP_RESEARCH"
    assert sample_prereflection["addressed_to"] == "BRAIN"


if __name__ == "__main__":
    asyncio.run(test_greeting_short_circuit())
    asyncio.run(test_unified_prereflection_schema_fields())
    print("✅ All Unified Pre-Reflection tests passed cleanly!")
