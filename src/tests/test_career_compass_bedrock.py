import os
import json
import pytest
from nodes.loader import BicameralNode

COMPASS_PATH = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/career_compass.json")


def test_career_compass_file_structure():
    """Verify that career_compass.json exists and contains valid Tier 1 & Tier 2 data."""
    assert os.path.exists(COMPASS_PATH), f"File not found: {COMPASS_PATH}"
    with open(COMPASS_PATH) as f:
        data = json.load(f)

    assert "tier_1_anchor_map" in data
    assert "tier_2_keyword_mesh" in data
    tier_1 = data["tier_1_anchor_map"]
    assert len(tier_1) >= 6, f"Expected at least 6 eras, got {len(tier_1)}"


def test_bicameral_node_bedrock_injection():
    """Verify that BicameralNode injects Tier 1 Anchor Map bedrock cleanly."""
    node = BicameralNode("test_compass_node", "Test prompt")
    assert "[CAREER_COMPASS_BEDROCK]:" in node.IDENTITY_BEDROCK
    assert "Manageability Test Content Lead" in node.IDENTITY_BEDROCK or "Era 2019 2024" in node.IDENTITY_BEDROCK


def test_tier_1_token_ceiling():
    """Enforce hard ceiling: Tier 1 Anchor Map bedrock MUST NOT exceed 350 tokens (~260 words)."""
    with open(COMPASS_PATH) as f:
        data = json.load(f)

    tier_1 = data.get("tier_1_anchor_map", {})
    full_text = json.dumps(tier_1)
    word_count = len(full_text.split())
    # 1.33 tokens per word estimation rule
    estimated_tokens = int(word_count * 1.33)

    assert estimated_tokens <= 350, (
        f"HARD CEILING EXCEEDED: Tier 1 Anchor Map estimated tokens = {estimated_tokens} "
        f"(word count: {word_count}). Must remain <= 350 tokens to prevent prompt bloat!"
    )


if __name__ == "__main__":
    test_career_compass_file_structure()
    test_bicameral_node_bedrock_injection()
    test_tier_1_token_ceiling()
    print("✅ All Career Compass Bedrock tests passed cleanly!")
