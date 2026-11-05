# [FEAT-434 / FEAT-075 / BKM-023 / BKM-085 / SPR-110]
# Unit tests for Decoupled Just-In-Time Career Compass Bedrock & Byte-Parity Verification

import hashlib
import pytest
from nodes.loader import BicameralNode, get_career_compass_bedrock
from logic.cognitive_hub import should_inject_career_bedrock, build_two_mice_stage_prompt


def test_bedrock_byte_parity():
    """Verify that get_career_compass_bedrock matches the exact immutable SHA256 baseline (zero paraphrasing)."""
    bedrock = get_career_compass_bedrock()
    assert len(bedrock) > 0, "Career compass bedrock must not be empty"
    h = hashlib.sha256(bedrock.encode("utf-8")).hexdigest()
    expected = "10bbbf8e107428a11d510be0bb637b9a0a65c58141f8ac773c7bf57adf27428b"
    assert h == expected, f"Paraphrasing/Byte Drift Detected! {h} != {expected}"


def test_node_identity_bedrock_omits_career():
    """Verify that BicameralNode does NOT bake career bedrock statically into IDENTITY_BEDROCK."""
    node = BicameralNode("test_pinky", "You are Pinky.")
    assert "[CAREER_COMPASS_BEDROCK]" not in node.IDENTITY_BEDROCK
    assert "[CAREER_COMPASS_BEDROCK]" not in node.system_prompt
    assert "Purley" not in node.IDENTITY_BEDROCK
    assert "DCMI" not in node.IDENTITY_BEDROCK
    assert "BMC" not in node.IDENTITY_BEDROCK


def test_should_inject_career_bedrock_deny_list():
    """Verify strict denial on operational, casual, and telemetry turns."""
    # Operational queries
    assert not should_inject_career_bedrock("OPERATIONAL", "exp_tlm")
    assert not should_inject_career_bedrock("OPERATIONAL", "telemetry")
    assert not should_inject_career_bedrock("OPERATIONAL", "infra")
    assert not should_inject_career_bedrock("OPERATIONAL", "Computer Architecture")

    # Casual / Banter queries
    assert not should_inject_career_bedrock("CASUAL", "social")
    assert not should_inject_career_bedrock("WYWO", "social")
    assert not should_inject_career_bedrock("", "social")


def test_should_inject_career_bedrock_allow_list():
    """Verify strict allowance on historical, chronicled, and career-specific turns."""
    assert should_inject_career_bedrock("HISTORICAL", "work_history")
    assert should_inject_career_bedrock("HISTORICAL", "career")
    assert should_inject_career_bedrock("HISTORICAL", "lab_history")
    assert should_inject_career_bedrock("CHRONICLE", "work_history")
    assert should_inject_career_bedrock("RETROSPECTIVE", "career_timeline")
    assert should_inject_career_bedrock("SOCRATIC", "career")
    assert should_inject_career_bedrock("SOCRATIC", "work_history", target_domains=["career_ledger"])


def test_build_two_mice_stage_prompt_conditional():
    """Verify build_two_mice_stage_prompt includes bedrock only when provided."""
    bedrock = get_career_compass_bedrock()

    # Without bedrock (Operational)
    prompt_op = build_two_mice_stage_prompt(1, user_query="Audit silicon", career_bedrock="")
    assert "[CAREER_COMPASS_BEDROCK]" not in prompt_op
    assert "Era 2005 2008" not in prompt_op

    # With bedrock (Historical)
    prompt_hist = build_two_mice_stage_prompt(1, user_query="What was my role in 2007?", career_bedrock=bedrock)
    assert "[CAREER_COMPASS_BEDROCK]" in prompt_hist
    assert "Era 2005 2008" in prompt_hist
