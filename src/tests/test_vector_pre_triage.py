import pytest
from logic.vector_pre_triage import probe_clara_dna_sync

def test_casual_greeting_probe():
    res = probe_clara_dna_sync("hi")
    assert "min_distance" in res
    assert "semantic_hint" in res
    assert res["min_distance"] > 0.60
    assert res["is_casual_candidate"] is True

def test_telemetry_probe():
    res = probe_clara_dna_sync("check GPU VRAM status and thermal levels")
    assert "min_distance" in res
    assert res["min_distance"] < 0.55
    assert res["best_collection"] in ["behavioral_dna", "feature_dna", "long_term_wisdom"]
    assert res["is_casual_candidate"] is False

def test_historical_rapl_probe():
    res = probe_clara_dna_sync("what did we do in 2018 for RAPL validation?")
    assert "min_distance" in res
    assert res["min_distance"] < 0.55
    assert res["is_casual_candidate"] is False
