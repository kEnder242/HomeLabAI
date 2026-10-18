"""[Story 105.11 / FEAT-523] Unit tests for ceiling-only headroom pacing & prompt de-fluffing.

Verifies:
  1. calculate_pacing_ceiling() ceiling math per node type (thought, critic, brain, pinky, default).
  2. calculate_pacing_range() backward-compat returns (0, ceiling).
  3. format_pacing_line() emits [BUDGET] ceiling-only text, NO 'Target ~low to high' floor text.
  4. build_two_mice_stage_prompt() stage 1 and stage 2 integration includes the new pacing line.
"""

import unittest

from logic.cognitive_hub import (
    calculate_pacing_ceiling,
    calculate_pacing_range,
    format_pacing_line,
    build_two_mice_stage_prompt,
)


class TestCalculatePacingCeiling(unittest.TestCase):
    """[FEAT-523] Continuous headroom ceiling math purely shaped by interest."""

    def test_ceiling_at_zero_interest(self):
        # When fuel is completely exhausted (interest 0.0), ceiling is 0
        self.assertEqual(calculate_pacing_ceiling("thought", 0.0), 0)
        self.assertEqual(calculate_pacing_ceiling("brain", 0.0), 0)
        self.assertEqual(calculate_pacing_ceiling("pinky", 0.0), 0)

    def test_ceiling_at_high_interest(self):
        # At max interest 1.0, ceiling is 1000 tokens across all personas
        self.assertEqual(calculate_pacing_ceiling("thought", 1.0), 1000)
        self.assertEqual(calculate_pacing_ceiling("deep_thought", 1.0), 1000)
        self.assertEqual(calculate_pacing_ceiling("brain", 1.0), 1000)
        self.assertEqual(calculate_pacing_ceiling("pinky", 1.0), 1000)

    def test_ceiling_at_mid_interest(self):
        # At mid interest 0.5, all personas receive identical 500 token ceiling
        self.assertEqual(calculate_pacing_ceiling("thought", 0.5), 500)
        self.assertEqual(calculate_pacing_ceiling("brain", 0.5), 500)
        self.assertEqual(calculate_pacing_ceiling("pinky", 0.5), 500)

    def test_ceiling_at_low_interest(self):
        # At interest 0.1, ceiling is 100 tokens
        self.assertEqual(calculate_pacing_ceiling("thought", 0.1), 100)
        self.assertEqual(calculate_pacing_ceiling("pinky", 0.1), 100)

    def test_interest_clamping_above_1(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", 1.5), 1000)

    def test_interest_clamping_below_0(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", -0.5), 0)



class TestCalculatePacingRangeBackwardCompat(unittest.TestCase):
    """calculate_pacing_range still returns (0, ceiling) for backward compat."""

    def test_thought_range(self):
        low, high = calculate_pacing_range("thought", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, calculate_pacing_ceiling("thought", 0.5))

    def test_critic_range(self):
        low, high = calculate_pacing_range("critic", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, calculate_pacing_ceiling("critic", 0.5))

    def test_brain_range(self):
        low, high = calculate_pacing_range("brain", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, calculate_pacing_ceiling("brain", 0.5))

    def test_pinky_range(self):
        low, high = calculate_pacing_range("pinky", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, calculate_pacing_ceiling("pinky", 0.5))


class TestFormatPacingLine(unittest.TestCase):
    """format_pacing_line emits [BUDGET] ceiling-only text with NO floor text."""

    def test_pinky_pacing_line_has_no_floor_text(self):
        line = format_pacing_line("pinky", 0.5)
        self.assertNotIn("Target ~", line)
        self.assertNotIn("[PACING]:", line)
        self.assertIn("[BUDGET]:", line)
        self.assertIn("Headroom ceiling is", line)
        self.assertIn("tokens", line)
        self.assertIn("Answer concisely within this budget", line)
        self.assertIn("do not add conversational fluff or filler", line)

    def test_thought_pacing_line_has_no_floor_text(self):
        line = format_pacing_line("thought", 0.8)
        self.assertNotIn("Target ~", line)
        self.assertNotIn("[PACING]:", line)
        self.assertIn("[BUDGET]:", line)
        self.assertIn("Headroom ceiling is", line)

    def test_brain_pacing_line_has_no_floor_text(self):
        line = format_pacing_line("brain", 0.3)
        self.assertNotIn("Target ~", line)
        self.assertNotIn("[PACING]:", line)
        self.assertIn("[BUDGET]:", line)
        self.assertIn("Headroom ceiling is", line)

    def test_critic_pacing_line_has_no_floor_text(self):
        line = format_pacing_line("critic", 0.5)
        self.assertNotIn("Target ~", line)
        self.assertNotIn("[PACING]:", line)
        self.assertIn("[BUDGET]:", line)
        self.assertIn("Headroom ceiling is", line)

    def test_pacing_line_contains_correct_ceiling_value(self):
        line = format_pacing_line("pinky", 0.5)
        expected = calculate_pacing_ceiling("pinky", 0.5)
        self.assertIn(f"Headroom ceiling is {expected} tokens", line)

    def test_pacing_line_is_single_line(self):
        line = format_pacing_line("pinky", 0.5)
        self.assertEqual(line.count("\n"), 0)


class TestStagePromptIntegration(unittest.TestCase):
    """build_two_mice_stage_prompt includes the new ceiling-only pacing line."""

    def test_stage1_prompt_contains_budget_ceiling(self):
        prompt = build_two_mice_stage_prompt(
            1,
            user_query="What is the firmware version?",
            context="Some archive data",
            interest=0.8,
        )
        self.assertIn("[BUDGET]:", prompt)
        self.assertIn("Headroom ceiling is", prompt)
        self.assertIn("Answer concisely within this budget", prompt)
        self.assertNotIn("Target ~", prompt)
        self.assertNotIn("[PACING]:", prompt)

    def test_stage2_prompt_contains_budget_ceiling(self):
        prompt = build_two_mice_stage_prompt(
            2,
            user_query="What is the firmware version?",
            brain_grounding="The firmware is v2.3.",
            interest=0.5,
        )
        self.assertIn("[BUDGET]:", prompt)
        self.assertIn("Headroom ceiling is", prompt)
        self.assertIn("Answer concisely within this budget", prompt)
        self.assertNotIn("Target ~", prompt)
        self.assertNotIn("[PACING]:", prompt)

    def test_stage1_prompt_uses_brain_ceiling(self):
        prompt = build_two_mice_stage_prompt(
            1, user_query="Test", context="Test", interest=1.0
        )
        expected = calculate_pacing_ceiling("brain", 1.0)
        self.assertIn(f"Headroom ceiling is {expected} tokens", prompt)

    def test_stage2_prompt_uses_pinky_ceiling(self):
        prompt = build_two_mice_stage_prompt(
            2, user_query="Test", brain_grounding="Test", interest=1.0
        )
        expected = calculate_pacing_ceiling("pinky", 1.0)
        self.assertIn(f"Headroom ceiling is {expected} tokens", prompt)


if __name__ == "__main__":
    unittest.main()
