import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


def resolve_hyde_vector(deep_thought_text: str = None, pinky_text: str = None, raw_query: str = ""):
    """3-Tier HyDE Failover Cascade Protocol [FEAT-437]."""
    if deep_thought_text and len(deep_thought_text.strip()) > 10:
        return deep_thought_text.strip(), "DEEP_THOUGHT_REMOTE"
    elif pinky_text and len(pinky_text.strip()) > 10:
        return pinky_text.strip(), "PINKY_LOCAL_VLLM"
    else:
        return raw_query.strip(), "DIRECT_RAW_QUERY"


def test_hyde_failover_cascade():
    """Verify 3-tier HyDE failover cascade resolution."""
    dt_text = "Intel Optane AEP mailbox automation script"
    pinky_text = "Narf! I think the user is asking about 2018 AEP"
    raw_q = "what did I do in 2018?"

    # Tier 1: Deep Thought Remote available
    vec, tier = resolve_hyde_vector(dt_text, pinky_text, raw_q)
    assert tier == "DEEP_THOUGHT_REMOTE"
    assert vec == dt_text

    # Tier 2: Deep Thought offline, Pinky Local available
    vec, tier = resolve_hyde_vector(None, pinky_text, raw_q)
    assert tier == "PINKY_LOCAL_VLLM"
    assert vec == pinky_text

    # Tier 3: Both offline/empty, Direct Raw Query fallback
    vec, tier = resolve_hyde_vector(None, None, raw_q)
    assert tier == "DIRECT_RAW_QUERY"
    assert vec == raw_q


@pytest.mark.asyncio
async def test_archive_node_hyde_parameter():
    """Verify get_context accepts hyde_vector_text parameter."""
    from nodes.archive_node import get_context
    assert "hyde_vector_text" in get_context.__code__.co_varnames


if __name__ == "__main__":
    test_hyde_failover_cascade()
    asyncio.run(test_archive_node_hyde_parameter())
    print("✅ All HyDE Plumbing & Failover Cascade tests passed cleanly!")
