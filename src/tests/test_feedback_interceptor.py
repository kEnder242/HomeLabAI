"""
[FEAT-456] Tests for Language-First Co-Pilot Feedback Loop (BKM-035)

Tests:
    1. Critique detection (is_critique) - BKM-015 compliant structural patterns
    2. Atomic JSONL ledger append (record_feedback) - BKM-022 atomic file swap
    3. Refinement prompt generation (generate_refinement_prompt) - BKM-035 flow
"""

import json
import os

from src.logic.feedback_interceptor import (
    is_critique,
    record_feedback,
    generate_refinement_prompt,
)


# ─── Critique Detection Tests (BKM-015 Compliant) ──────────────────────────

class TestIsCritique:
    """Test structural critique detection patterns."""

    def test_direct_correction_wait_wrong(self):
        """Detect 'Wait, that's wrong' pattern."""
        assert is_critique("Wait, that's wrong, RAPL MSR 0x610 is PKG limit") is True

    def test_direct_correction_no_incorrect(self):
        """Detect 'No, that's incorrect' pattern."""
        assert is_critique("No, that's incorrect, the register is 0x600") is True

    def test_actually_correction(self):
        """Detect 'Actually X is Y' pattern."""
        assert is_critique("Actually the default timeout is 30 seconds") is True

    def test_fourth_wall_pinky_address(self):
        """Detect 'Pinky, note that' fourth-wall address pattern."""
        assert is_critique("Pinky, note that your triage missed the AER register") is True

    def test_fourth_wall_brain_address(self):
        """Detect 'Brain, you're wrong' fourth-wall address pattern."""
        assert is_critique("Brain, you're wrong about the VRAM allocation") is True

    def test_negation_correction(self):
        """Detect 'X is not Y, it's Z' correction pattern."""
        assert is_critique("That is not the right approach, it should be recursive") is True

    def test_disagreement_marker(self):
        """Detect 'I disagree' marker."""
        assert is_critique("I disagree with that assessment") is True

    def test_not_right_pattern(self):
        """Detect 'That's not right' pattern."""
        assert is_critique("That's not right, the port is 8001") is True

    def test_clarify_correction(self):
        """Detect 'To clarify' correction pattern."""
        assert is_critique("To clarify: that is the wrong adapter") is True

    def test_beg_to_differ(self):
        """Detect 'I beg to differ' pattern."""
        assert is_critique("I beg to differ, the load average was 2.5") is True

    def test_positive_detection_returns_true(self):
        """Any critique pattern should return True."""
        assert is_critique("Actually, the correct answer is 42") is True

    # ─── Non-Critique Cases (Should Return False) ────────────────────────────

    def test_normal_question(self):
        """Normal technical question is not a critique."""
        assert is_critique("What is the VRAM usage on the 2080 Ti?") is False

    def test_greeting(self):
        """Casual greeting is not a critique."""
        assert is_critique("Hey Pinky, how are you today?") is False

    def test_positive_feedback(self):
        """Positive feedback is not a critique."""
        assert is_critique("That's correct, good job on the thermal analysis") is False

    def test_empty_string(self):
        """Empty string is not a critique."""
        assert is_critique("") is False

    def test_none_like_empty(self):
        """Whitespace-only string is not a critique."""
        assert is_critique("   ") is False

    def test_technical_query_with_actually(self):
        """'Actually' in non-correction context is not a critique."""
        # This is a question, not a correction
        assert is_critique("Actually, can you check the logs?") is False

    def test_no_domain_keywords(self):
        """Verify detection works without domain-specific keywords."""
        # BKM-015: structural patterns, not domain keywords
        assert is_critique("Wait, that's wrong") is True
        assert is_critique("The register is 0x610") is False


# ─── Atomic JSONL Ledger Tests (BKM-022 Compliant) ─────────────────────────

class TestRecordFeedback:
    """Test atomic JSONL ledger append operations."""

    def test_record_append_creates_file(self, tmp_path):
        """Verify FAIL record is created in a new JSONL file."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        record = record_feedback(
            query="What is the thermal limit?",
            flawed_output="The thermal limit is 90C",
            user_correction="The thermal limit is 83C for Turing",
            ledger_path=ledger_path,
        )

        assert os.path.exists(ledger_path)
        assert record["verdict"] == "FAIL"
        assert record["source"] == "CO_PILOT_FOURTH_WALL"

    def test_record_schema_completeness(self, tmp_path):
        """Verify all required BKM-035 schema fields are present."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        record = record_feedback(
            query="Test query",
            flawed_output="Test flawed output",
            user_correction="Test correction",
            ledger_path=ledger_path,
        )

        required_fields = [
            "timestamp", "query", "verdict", "flawed_output",
            "ground_truth", "source", "previous_user_input", "previous_full_turn"
        ]
        for field in required_fields:
            assert field in record, f"Missing required field: {field}"

        assert record["timestamp"].endswith("Z") or "+" in record["timestamp"]

    def test_record_captures_prior_full_turn(self, tmp_path):
        """Verify full previous turn and triage metadata are logged."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        record = record_feedback(
            query="fallback query",
            flawed_output="Narf! Hello human! I am Pinky and here is a giant essay...",
            user_correction="feedback: your last response was too verbose",
            ledger_path=ledger_path,
            previous_user_input="hi there",
            previous_full_turn="User: hi there\nPinky: Narf! Hello human! I am Pinky...",
            previous_triage={"vibe": "CASUAL", "addressed_to": "NONE", "inferred_intent": "greeting"}
        )

        assert record["previous_user_input"] == "hi there"
        assert record["query"] == "hi there"
        assert "User: hi there" in record["previous_full_turn"]
        assert record["previous_triage"]["vibe"] == "CASUAL"
        assert record["ground_truth"] == "feedback: your last response was too verbose"

    def test_record_is_valid_jsonl(self, tmp_path):
        """Verify written file contains valid JSONL (one JSON per line)."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        record_feedback(
            query="Query 1",
            flawed_output="Flawed 1",
            user_correction="Correction 1",
            ledger_path=ledger_path,
        )
        record_feedback(
            query="Query 2",
            flawed_output="Flawed 2",
            user_correction="Correction 2",
            ledger_path=ledger_path,
        )

        with open(ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line.strip())
            assert parsed["verdict"] == "FAIL"

    def test_atomic_no_temp_residue(self, tmp_path):
        """Verify no .tmp files remain after successful write (BKM-022)."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        record_feedback(
            query="Test",
            flawed_output="Flawed",
            user_correction="Fix",
            ledger_path=ledger_path,
        )

        # Check no .tmp files remain
        tmp_files = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
        assert len(tmp_files) == 0, f"Residual .tmp files found: {tmp_files}"

    def test_record_preserves_existing_content(self, tmp_path):
        """Verify append doesn't overwrite existing ledger content."""
        ledger_path = str(tmp_path / "validation_ledger.jsonl")

        # Write first record
        record_feedback(
            query="First query",
            flawed_output="First flawed",
            user_correction="First correction",
            ledger_path=ledger_path,
        )

        # Write second record
        record_feedback(
            query="Second query",
            flawed_output="Second flawed",
            user_correction="Second correction",
            ledger_path=ledger_path,
        )

        with open(ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2
        first_record = json.loads(lines[0])
        second_record = json.loads(lines[1])
        assert first_record["query"] == "First query"
        assert second_record["query"] == "Second query"

    def test_default_ledger_path(self):
        """Verify default ledger path matches BKM-035 spec."""
        from src.logic.feedback_interceptor import _DEFAULT_LEDGER_PATH

        expected = os.path.expanduser(
            "~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl"
        )
        assert _DEFAULT_LEDGER_PATH == expected


# ─── Refinement Prompt Generation Tests (BKM-035 Flow) ─────────────────────

class TestGenerateRefinementPrompt:
    """Test Pinky's in-character acknowledgment generation."""

    def test_acknowledgment_includes_correction(self):
        """Verify the correction text appears in the acknowledgment."""
        prompt = generate_refinement_prompt(
            "MSR 0x610 is the PKG energy limit, not DRAM"
        )

        assert "Narf!" in prompt
        assert "MSR 0x610" in prompt
        assert "PKG energy limit" in prompt

    def test_follow_up_question_present(self):
        """Verify one targeted follow-up question is included."""
        prompt = generate_refinement_prompt("The timeout is 30 seconds")

        # Should contain a question mark (the follow-up)
        assert "?" in prompt
        # Should ask about boundary conditions or register masks
        assert "register mask" in prompt or "query scope" in prompt

    def test_strips_pinky_address(self):
        """Verify 'Pinky, ' prefix is stripped from correction text."""
        prompt = generate_refinement_prompt(
            "Pinky, note that your triage missed the AER register"
        )

        # The acknowledgment should not include "Pinky, note that"
        assert "Narf! Got it —" in prompt
        assert "Pinky, note that" not in prompt.split("Narf!")[1]

    def test_no_defensiveness(self):
        """Verify response contains no defensive language."""
        prompt = generate_refinement_prompt("You're wrong about everything")

        defensive_words = ["but", "however", "actually", "well", "I think"]
        prompt_lower = prompt.lower()
        for word in defensive_words:
            # Should not start sentences with defensive hedging
            assert not prompt_lower.startswith(word)

    def test_brevity(self):
        """Verify response is concise (BKM-035: high brevity)."""
        prompt = generate_refinement_prompt("Simple correction")

        # Should be under 200 characters
        assert len(prompt) < 200

    def test_various_correction_styles(self):
        """Verify response handles different correction input styles."""
        # Technical correction
        prompt1 = generate_refinement_prompt(
            "The CUDA compute capability is 7.5, not 8.0"
        )
        assert "Narf!" in prompt1

        # Behavioral correction
        prompt2 = generate_refinement_prompt(
            "You should not have used the wrong adapter"
        )
        assert "Narf!" in prompt2
