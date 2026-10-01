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
    assert res["best_collection"] in [
        "behavioral_dna",
        "feature_dna",
        "long_term_wisdom",
    ]
    assert res["is_casual_candidate"] is False


def test_historical_rapl_probe():
    res = probe_clara_dna_sync("what did we do in 2018 for RAPL validation?")
    assert "min_distance" in res
    assert res["min_distance"] < 0.55
    assert res["is_casual_candidate"] is False


def test_zero_dna_probe_bypass():
    # [FEAT-540 / Story 96.2] Immediate 0ms bypass for explicit ZERO DNA
    res = probe_clara_dna_sync("check architecture specs", collections=[])
    assert res["min_distance"] == 1.0
    assert res["best_collection"] == ""
    assert res["results_by_collection"] == {}
    assert res["is_casual_candidate"] is True
    assert "[ZERO_DNA]" in res["semantic_hint"]


def test_filtered_collections_probe():
    # [FEAT-540 / Story 96.2] Constrained multi-collection probe
    res = probe_clara_dna_sync(
        "check GPU VRAM status", collections=["behavioral_dna"]
    )
    assert "behavioral_dna" in res["results_by_collection"]
    # Verify unrequested collections are not probed
    assert "career_ledger" not in res["results_by_collection"]
    assert "philosophy_dna" not in res["results_by_collection"]

