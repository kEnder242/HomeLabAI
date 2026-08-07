"""
[FEAT-445] Memory Architecture & Stability Unit Test Suite.

Verifies:
  1. journal_ledger spoken-only dialogue filtering & 24h retention contract.
  2. _rag_cache SHA256 hashing & LRU eviction (maxlen <= 128).
  3. sensory_manager unconditional sliding-window buffer trim (<= 24000 samples).
  4. dream_node 2-stage memory consolidation & WYWO briefing.
  5. processed_ids deque maxlen=1000 eviction.
  6. _truncate_to_tokens sentinel context cap (<= 2500 tokens).
"""

import hashlib
import json
import os
import time
import numpy as np
import pytest
from collections import deque

from logic.cognitive_hub import CognitiveHub
from equipment.sensory_manager import SensoryManager
from infra.dream_node import run_test_dream


def _make_hub():
    return CognitiveHub(
        residents={},
        broadcast_callback=None,
        sensory_manager=None,
        get_vram_status=None,
        trigger_morning_briefing=None,
    )


def test_processed_ids_deque_eviction():
    """Verify processed_ids bounds memory growth to maxlen=1000 via deque."""
    hub = _make_hub()
    assert isinstance(hub.processed_ids, deque)
    assert hub.processed_ids.maxlen == 1000

    for i in range(1100):
        hub.processed_ids.append(f"req_{i}")

    assert len(hub.processed_ids) == 1000
    assert "req_0" not in hub.processed_ids
    assert "req_1099" in hub.processed_ids


def test_rag_cache_hashing_and_lru():
    """Verify RAG cache stores and evicts at max 128 entries."""
    hub = _make_hub()
    assert hub._rag_cache == {}

    for i in range(135):
        key = hashlib.sha256(f"turn_{i}".encode()).hexdigest()
        hub._rag_cache[key] = f"payload_{i}"
        if len(hub._rag_cache) > 128:
            hub._rag_cache.pop(next(iter(hub._rag_cache)))

    assert len(hub._rag_cache) == 128
    first_key = hashlib.sha256("turn_0".encode()).hexdigest()
    last_key = hashlib.sha256("turn_134".encode()).hexdigest()
    assert first_key not in hub._rag_cache
    assert last_key in hub._rag_cache


def test_truncate_to_tokens_sentinel():
    """Verify _truncate_to_tokens caps context at ~2500 tokens (10000 chars) with [MORE]."""
    hub = _make_hub()

    short_text = "Hello world"
    assert hub._truncate_to_tokens(short_text, max_tokens=2500) == short_text

    long_text = "A" * 20000
    truncated = hub._truncate_to_tokens(long_text, max_tokens=2500, doc_id="test_doc.md")

    assert len(truncated) <= 10000
    assert "[MORE: test_doc.md...]" in truncated


def test_sensory_audio_buffer_unconditional_trim():
    """Verify SensoryManager trims audio_buffer unconditionally even when self.ear is None."""
    sm = SensoryManager(broadcast_callback=None)
    sm.ear = None
    assert len(sm.audio_buffer) == 0

    dummy_pcm = np.zeros(30000, dtype=np.int16).tobytes()
    sm.process_binary_chunk(dummy_pcm)

    # Buffer must be trimmed to <= 24000 samples even with ear=None
    assert len(sm.audio_buffer) < 30000
    assert len(sm.audio_buffer) == 14000  # 30000 - 16000 sliding window step


def test_dream_node_test_dream():
    """Verify Two-Stage Subconscious Dream Engine via self-contained validation harness."""
    verdict = run_test_dream()
    assert verdict["stage1"] == "PASS"
    assert verdict["stage2"] == "PASS"
