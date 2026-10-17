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
    """Ceiling-only headroom math for each node type."""

    def test_thought_ceiling_at_low_interest(self):
        self.assertEqual(calculate_pacing_ceiling("thought", 0.0), 300)

    def test_thought_ceiling_at_high_interest(self):
        self.assertEqual(calculate_pacing_ceiling("thought", 1.0), 800)

    def test_thought_ceiling_at_mid_interest(self):
        self.assertEqual(calculate_pacing_ceiling("thought", 0.5), 550)

    def test_deep_alias_maps_to_thought(self):
        self.assertEqual(calculate_pacing_ceiling("deep_thought", 1.0), 800)

    def test_critic_ceiling_is_stable(self):
        self.assertEqual(calculate_pacing_ceiling("critic", 0.0), 100)
        self.assertEqual(calculate_pacing_ceiling("critic", 0.5), 100)
        self.assertEqual(calculate_pacing_ceiling("critic", 1.0), 100)

    def test_brain_ceiling_at_low_interest(self):
        self.assertEqual(calculate_pacing_ceiling("brain", 0.0), 80)

    def test_brain_ceiling_at_high_interest(self):
        self.assertEqual(calculate_pacing_ceiling("brain", 1.0), 250)

    def test_brain_ceiling_at_mid_interest(self):
        self.assertEqual(calculate_pacing_ceiling("brain", 0.5), 165)

    def test_pinky_ceiling_at_low_interest(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", 0.0), 60)

    def test_pinky_ceiling_at_high_interest(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", 1.0), 200)

    def test_default_ceiling_at_low_interest(self):
        self.assertEqual(calculate_pacing_ceiling("unknown_node", 0.0), 60)

    def test_interest_clamping_above_1(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", 1.5), 200)

    def test_interest_clamping_below_0(self):
        self.assertEqual(calculate_pacing_ceiling("pinky", -0.5), 60)


class TestCalculatePacingRangeBackwardCompat(unittest.TestCase):
    """calculate_pacing_range still returns (0, ceiling) for backward compat."""

    def test_thought_range(self):
        low, high = calculate_pacing_range("thought", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, calculate_pacing_ceiling("thought", 0.5))

    def test_critic_range(self):
        low, high = calculate_pacing_range("critic", 0.5)
        self.assertEqual(low, 0)
        self.assertEqual(high, 100)

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
