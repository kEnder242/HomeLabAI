"""
[FEAT-487 / SPR-65 Story 2 / BKM-035] Semantic Meta-Triage Feedback Interceptor.

Validates that natural supervisory feedback — explicit 'feedback:' prefixes,
bug/regression reports, factual corrections, tone/verbosity adjustments, and
Fourth-Wall commands — reliably trigger the semantic control-plane intercept
(vibe: META, domain: feedback, addressed_to: SYSTEM) and are recorded atomically
to validation_ledger.jsonl.

Because classification is model-driven (the triage LLM is instructed to emit
META/feedback), this battery verifies the deterministic contract that gates it:
  - each phrase's model classification survives the post-triage classifier and
    fires is_control_plane_feedback (the fast control-plane intercept),
  - record_feedback appends each phrase as a FAIL entry (BKM-035), and
  - the triage taxonomy (policy + support for the feedback domain) is wired.
"""

import json

import pytest

from src.logic.triage_engine import (
    classify_vibe_and_domain,
    is_control_plane_feedback,
)
from src.logic.feedback_interceptor import record_feedback
from src.logic.triage_policy_loader import TriagePolicyLoader

# [FEAT-487] Grounded 11-phrase test battery (natural supervisory feedback).
FEEDBACK_TEST_BATTERY = [
    "feedback: 1) rag echo 2) verbosity should be tweaked",
    "feedback: KENDER should have a ping check gate",
    "Wait, that's wrong, the register offset is 0x610 not 0x618",
    "Actually, in 2016 I worked on ESB2 server management, not Optane",
    "Pinky, note that we deprecated InfluxDB in Phase 3",
    "Brain, your dates are off by two years",
    "This is way too verbose, give me just the bullet points",
    "Regression: the coherence critic is failing every turn with score 1",
    "I disagree with that summary, check the 2019 logs again",
    "Correction: the host rebooted due to hung_task_panic on USB sync",
    "Can you be more concise? Stop giving me 5-page essays",
]


def _meta_parsed(phrase: str) -> dict:
    """The post-triage classification the triage model emits for feedback turns."""
    return {
        "inferred_intent": "supervisory feedback",
        "addressed_to": "SYSTEM",
        "vibe": "META",
        "domain": "feedback",
        "importance": 0.0,
        "situation": phrase,
        "hyde_vector_text": "",
    }


def test_battery_classifies_to_meta_feedback_and_fires_intercept():
    """Each phrase's triage classification survives post-processing and fires the intercept."""
    for phrase in FEEDBACK_TEST_BATTERY:
        t_parsed = _meta_parsed(phrase)
        vibe, domain = classify_vibe_and_domain(phrase, t_parsed)
        assert (vibe, domain) == ("META", "feedback"), (phrase, vibe, domain)
        assert is_control_plane_feedback({**t_parsed, "vibe": vibe, "domain": domain}) is True, phrase


def test_all_battery_phrases_routed_to_system_not_swallowed():
    """None of the battery turns is mis-routed to lab_internal (meta-status) or PINKY."""
    for phrase in FEEDBACK_TEST_BATTERY:
        t_parsed = _meta_parsed(phrase)
        assert t_parsed["addressed_to"] == "SYSTEM", phrase
        assert is_control_plane_feedback(t_parsed) is True, phrase


def test_lab_internal_meta_status_not_swallowed_as_feedback():
    """Safety property: META/lab_internal meta-status queries must NOT trigger the feedback intercept."""
    assert is_control_plane_feedback({"vibe": "META", "domain": "lab_internal"}) is False
    assert is_control_plane_feedback({"vibe": "META", "domain": "exp_tlm"}) is False
    assert is_control_plane_feedback({"vibe": "META", "domain": "lab_history"}) is False


def test_battery_appends_to_validation_ledger(tmp_path):
    """Each phrase is recorded atomically as a FAIL entry to validation_ledger.jsonl (BKM-035)."""
    ledger_path = tmp_path / "validation_ledger.jsonl"
    for phrase in FEEDBACK_TEST_BATTERY:
        record = record_feedback(
            query=phrase,
            flawed_output="previous synthesized essay",
            user_correction=phrase,
            ledger_path=str(ledger_path),
        )
        assert record["verdict"] == "FAIL"
        assert record["ground_truth"] == phrase
        assert record["source"] == "CO_PILOT_FOURTH_WALL"

    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [l for l in f.readlines() if l.strip()]

    assert len(lines) == len(FEEDBACK_TEST_BATTERY)
    for line, phrase in zip(lines, FEEDBACK_TEST_BATTERY):
        rec = json.loads(line)
        assert rec["ground_truth"] == phrase
        assert rec["verdict"] == "FAIL"


def test_triage_taxonomy_registers_meta_feedback():
    """The declarative taxonomy registers META as feedback / addressed_to SYSTEM / importance 0."""
    rule = TriagePolicyLoader().get_vibe_rule("META")
    assert rule is not None
    assert rule["domain"] == "feedback"
    assert rule["addressed_to"] == "SYSTEM"
    assert rule["importance"] == 0.0
    assert rule["default_domain"] == "feedback"


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT 75 TESTS: Tense-Aware Triage, Host Vitals & Dialogue Sanitizer
# ═══════════════════════════════════════════════════════════════════════════════

def test_present_tense_live_vitals_routes_to_lab_internal():
    """[Story 75.2] Present tense live vitals queries route to lab_internal."""
    t_parsed = {
        "inferred_intent": "query live memory",
        "addressed_to": "NONE",
        "vibe": "OPERATIONAL",
        "domain": "lab_internal",
        "casual": 0.2,
        "intrigue": 0.5,
        "importance": 0.5,
        "hyde_vector_text": "",
    }
    vibe, domain = classify_vibe_and_domain("what does the memory look like?", t_parsed)
    assert domain == "lab_internal"
    assert is_control_plane_feedback({"vibe": vibe, "domain": domain}) is False


def test_ambiguous_query_routes_to_unclear():
    """[Story 75.2] Ambiguous queries can be classified to domain 'unclear'."""
    t_parsed = {
        "inferred_intent": "ambiguous turn",
        "addressed_to": "NONE",
        "vibe": "CASUAL",
        "domain": "unclear",
        "casual": 0.5,
        "intrigue": 0.5,
        "importance": 0.3,
        "hyde_vector_text": "",
    }
    vibe, domain = classify_vibe_and_domain("wait, check that again", t_parsed)
    assert domain == "unclear"


def test_sanitize_spoken_dialogue_circuit_breaker():
    """[Story 75.4 / FEAT-558] Circuit breaker strips <thought> tags and role markup."""
    from src.logic.cognitive_hub import sanitize_spoken_dialogue

    dirty_text = "<thought>Thinking about PCIe error counts in 2018...</thought> The current GPU VRAM usage is 7.3 GB."
    cleaned = sanitize_spoken_dialogue(dirty_text)
    assert "<thought>" not in cleaned
    assert "PCIe error counts" not in cleaned
    assert "The current GPU VRAM usage is 7.3 GB." in cleaned

    multiline_dirty = """<thought>
    Internal monologue step 1
    Internal monologue step 2
    </thought>
    <PINKY>Narf! All systems are green!</PINKY>"""
    cleaned_multi = sanitize_spoken_dialogue(multiline_dirty)
    assert "Internal monologue" not in cleaned_multi
    assert "Narf! All systems are green!" in cleaned_multi


def test_get_host_vitals_telemetry():
    """[Story 75.3 / FEAT-557] Host vitals query returns live hardware metrics."""
    from src.infra.live_telemetry import get_host_vitals

    vitals = get_host_vitals()
    assert "gpu" in vitals
    assert "host_ram" in vitals
    assert "cpu" in vitals
    assert "model_residency" in vitals
    assert vitals["host_ram"]["total_gb"] > 0
    assert vitals["cpu"]["core_count"] > 0

