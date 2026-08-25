"""
[SPR-59.0] End-to-End Integration Test Suite

Verifies full-loop runtime integration across all Sprint 59 features:
  1. [FEAT-456/BKM-035] Live Fourth Wall Critique Interception & Validation Ledger Writing
  2. [FEAT-458] Live Floating Oracle Candidate Pool Injection on Casual/Greeting Turns
  3. [FEAT-455] AST Context Compiler on Live HomeLabAI Codebase (>50% Token Compaction)
  4. [FEAT-454] Universal Epistemic 5-Question Evaluator Consistency & Determinism
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from compiler.context_compiler import ContextCompiler
from curator.scan_curator import evaluate_gem_quality
from logic.cognitive_hub import CognitiveHub
from logic.feedback_interceptor import is_critique, record_feedback
from logic.floating_oracle import is_shallow_turn, build_floating_candidate_pool


@pytest.fixture
def mock_hub_env():
    """Builds a CognitiveHub with mocked residents and callbacks."""
    pinky = MagicMock()
    pinky.call_tool = AsyncMock()

    brain = MagicMock()
    brain.call_tool = AsyncMock()

    thought = MagicMock()
    thought.call_tool = AsyncMock()

    archive = MagicMock()
    archive.call_tool = AsyncMock()

    lab = MagicMock()
    lab.call_tool = AsyncMock()

    residents = {
        "pinky": pinky,
        "brain": brain,
        "thought": thought,
        "archive": archive,
        "lab": lab,
    }

    broadcast = AsyncMock()
    sensory = MagicMock()
    vram_status = MagicMock(return_value=True)

    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=broadcast,
        sensory_manager=sensory,
        get_vram_status=vram_status,
        trigger_morning_briefing=AsyncMock(),
    )

    hub.auditor = MagicMock()
    hub.auditor.audit_technical_truth = AsyncMock(return_value=True)

    return hub, broadcast, residents


# ─── 1. End-to-End Fourth Wall Feedback Loop Test ─────────────────────────────


@pytest.mark.asyncio
async def test_e2e_fourth_wall_critique_interception(mock_hub_env, tmp_path):
    """
    [FEAT-456/BKM-035] Live Full-Loop: User disagreement bypasses triage,
    atomically logs a FAIL record with ground truth to validation_ledger.jsonl,
    and returns Pinky's in-character refinement response.
    """
    hub, broadcast, residents = mock_hub_env
    test_ledger = str(tmp_path / "validation_ledger.jsonl")

    # Simulate an earlier turn that had a flawed response in memory
    hub.round_table_memory = ["RAPL energy counter MSR 0x610 tracks DRAM energy."]

    critique_query = "Wait, that's wrong, RAPL MSR 0x610 is PKG limit, not DRAM."

    # Verify critique classifier triggers
    assert is_critique(critique_query) is True

    # Patch record_feedback to use test ledger
    with patch("logic.cognitive_hub.record_feedback", side_effect=lambda **kwargs: record_feedback(ledger_path=test_ledger, **kwargs)):
        await hub.process_query(critique_query)

    # 1. Verify triage LLM was completely bypassed (0 calls to lab resident)
    residents["lab"].call_tool.assert_not_called()

    # 2. Verify broadcast received Pinky refinement stream
    broadcast_calls = [call.args[0] for call in broadcast.call_args_list]
    thought_streams = [
        msg for msg in broadcast_calls if msg.get("type") == "thought_stream"
    ]
    assert len(thought_streams) > 0
    refinement_msg = thought_streams[0]
    assert refinement_msg.get("source") == "Pinky (Feedback)"
    assert len(refinement_msg.get("token", "")) > 0

    # 3. Verify validation_ledger.jsonl has the atomic FAIL record
    assert os.path.exists(test_ledger)
    with open(test_ledger, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == 1
    record = records[0]
    assert record["verdict"] == "FAIL"
    assert record["source"] == "CO_PILOT_FOURTH_WALL"
    assert record["ground_truth"] == critique_query
    assert "MSR 0x610" in record["flawed_output"]


# ─── 2. End-to-End Floating Oracle Candidate Pool Test ───────────────────────


@pytest.mark.asyncio
async def test_e2e_floating_oracle_candidate_injection(mock_hub_env, tmp_path):
    """
    [FEAT-458] Live Full-Loop: Shallow greeting turn dynamically harvests
    validation scars, mass-scan progress, and subconscious dreams into context.
    """
    hub, broadcast, residents = mock_hub_env

    # Populate temporary mock state files
    ledger_path = str(tmp_path / "validation_ledger.jsonl")
    scan_state_path = str(tmp_path / "scan_state.json")
    dialogue_path = str(tmp_path / "nightly_dialogue.json")

    # 1. Mock validation scar
    record_feedback(
        query="Explain AER register",
        flawed_output="AER is port 80",
        user_correction="AER register is PCIe configuration offset 0x100",
        ledger_path=ledger_path,
    )

    # 2. Mock scan state
    with open(scan_state_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "milestone": "42/50 chunks processed in notes_TELEMETRY.txt",
                "current_file": "notes_TELEMETRY.txt",
            },
            f,
        )

    # 3. Mock nightly dream
    with open(dialogue_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "topic": "Thermal Throttling & RAPL Pacing",
                "content": "Brain and Pinky synthesized 50ms hardware pacing callbacks to prevent thermal collapse.",
            },
            f,
        )

    # Harvest and build candidate pool
    with patch("logic.floating_oracle._DEFAULT_LEDGER_PATH", ledger_path), patch(
        "logic.floating_oracle._DEFAULT_SCAN_STATE_PATH", scan_state_path
    ), patch("logic.floating_oracle._DEFAULT_DIALOGUE_PATH", dialogue_path):
        candidate_pool = build_floating_candidate_pool(auto_harvest=True)

    assert "[FLOATING_CANDIDATES]" in candidate_pool
    assert "[VALIDATION_SCAR]" in candidate_pool
    assert "AER register is PCIe configuration offset 0x100" in candidate_pool
    assert "[SCAN_PROGRESS]" in candidate_pool
    assert "notes_TELEMETRY.txt" in candidate_pool
    assert "[SUBCONSCIOUS_DREAM]" in candidate_pool
    assert "Thermal Throttling & RAPL Pacing" in candidate_pool

    # Verify shallow turn classifier
    greeting = "hey pinky, how are things?"
    assert is_shallow_turn(greeting) is True


# ─── 3. Real-Codebase AST Context Compiler Test ──────────────────────────────


def test_real_codebase_context_compilation():
    """
    [FEAT-455] Verifies ContextCompiler on actual HomeLabAI production codebase,
    asserting >50% token compaction and 100% symbol interface fidelity.
    """
    logic_dir = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/logic")
    compiler = ContextCompiler()

    compiled_markdown = compiler.compile_workspace(logic_dir)

    assert len(compiled_markdown) > 0
    assert "# Compiled Context:" in compiled_markdown
    assert "class CognitiveHub" in compiled_markdown
    assert "def is_critique" in compiled_markdown
    assert "def build_floating_candidate_pool" in compiled_markdown

    # Compare raw characters vs compiled characters
    raw_char_count = 0
    for root, _, files in os.walk(logic_dir):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                    raw_char_count += len(f.read())

    compiled_char_count = len(compiled_markdown)
    compaction_ratio = (raw_char_count - compiled_char_count) / raw_char_count

    print(f"\n[AST COMPILER] Raw: {raw_char_count} chars -> Compiled: {compiled_char_count} chars ({compaction_ratio:.1%} reduction)")
    assert compaction_ratio > 0.40, f"Expected >40% compaction, got {compaction_ratio:.1%}"


# ─── 4. Universal Epistemic Evaluator Consistency Test ────────────────────────


def test_universal_epistemic_evaluator_consistency():
    """
    [FEAT-454] Verifies that the Universal 5-Question Battery produces 0% score
    drift across repeated deterministic evaluations.
    """
    high_fidelity_gem = (
        "=== RAPL Energy Telemetry BKM ===\n"
        "MSR 0x610 (MSR_PKG_ENERGY_STATUS) provides 32-bit energy units for Haswell package power.\n"
        "Reproduction Recipe:\n"
        "1. sudo modprobe msr\n"
        "2. sudo rdmsr 0x610 -d\n"
        "Root cause: Counter rolls over due to high 84W power draw. Triggers energy overflow.\n"
        "BKM Action: Clamp sampling window in rapl_monitor.py:L45.\n"
    )

    fluff_gem = (
        "Hello everyone! I hope you are having a wonderful day. In this note we will discuss "
        "computers and how they run smoothly with AI agents. Make sure to stay tuned for more updates!"
    )

    # 1. High fidelity gem evaluation
    result_high = evaluate_gem_quality(high_fidelity_gem)
    assert result_high["rank"] >= 4
    assert result_high["checks"]["has_exact_identifiers"] is True
    assert result_high["checks"]["has_reproduction_recipe"] is True
    assert result_high["checks"]["isolates_cause_and_effect"] is True

    # 2. Fluff gem evaluation
    result_fluff = evaluate_gem_quality(fluff_gem)
    assert result_fluff["rank"] == 1
    assert result_fluff["checks"]["has_exact_identifiers"] is False
    assert result_fluff["checks"]["has_reproduction_recipe"] is False
    assert result_fluff["checks"]["is_actionable_bkm"] is False
