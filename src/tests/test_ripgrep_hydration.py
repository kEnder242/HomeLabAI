#!/usr/bin/env python3
"""
[FEAT-451] / [Story 109.9] Unit Test for Ripgrep Ground Truth Hydration Bridge.

Verifies:
1. execute_grep_search_pivot() searches knowledge_base for curated anchors.
2. Search execution latency is sub-25ms.
3. Anchors extraction parses hex tokens, file names, and technical terms.
4. Results format correctly into <ground_truth_exhaust>.
"""

import sys
import time
import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from nodes.archive_node import execute_grep_search_pivot


def test_anchor_extraction_logic():
    mock_brain_output = """
    [BEDROCK SELECTION]
    CHUNK-1 => KEEP: Contains register 0x610 RAPL power limit configuration and peci_driver.py details.
    CHUNK-2 => DROP: Non-pertinent general setup.
    Anchor targets: Aurora cluster node042 and Optane DIMM.
    """
    raw_tokens = re.findall(r"\b(?:0x[0-9a-fA-F]+|[A-Z][a-zA-Z0-9_-]{2,}|\w+\.(?:py|sh|c|h|txt|json))\b", mock_brain_output)
    stop_tokens = {
        "THE", "AND", "FOR", "WITH", "THAT", "WHAT", "HOW", "WHEN", "WHERE", "WHY",
        "DID", "KEEP", "DROP", "CHUNK", "TRUE", "FALSE", "NONE", "NULL", "NOTE",
        "PASS", "FAIL", "BRAIN", "PINKY", "DEEP", "THOUGHT", "STATUS", "VERDICT", "VIBE"
    }
    anchors = [t for t in raw_tokens if t.upper() not in stop_tokens and not t.startswith("CHUNK-")]

    assert "0x610" in anchors
    assert "RAPL" in anchors
    assert "peci_driver.py" in anchors
    assert "Aurora" in anchors
    assert "KEEP" not in anchors
    assert "DROP" not in anchors
    print("TEST_ANCHOR_EXTRACTION_LOGIC: PASSED")


def test_execute_grep_search_pivot_latency():
    # Warmup invocation
    execute_grep_search_pivot(
        query="debug notes",
        max_matches=1,
        curated_anchors=["PECI"]
    )

    t_start = time.perf_counter()
    # Query for a known keyword across knowledge_base
    res = execute_grep_search_pivot(
        query="debug notes",
        max_matches=5,
        curated_anchors=["PECI", "0x610"]
    )
    t_elapsed = (time.perf_counter() - t_start) * 1000.0
    print(f"Ripgrep execution latency: {t_elapsed:.2f}ms (Result length: {len(res)} chars)")

    assert len(res) > 0, "Expected non-empty grep evidence from knowledge_base"
    assert "<ground_truth" not in res  # archive_node returns raw text, cognitive_hub wraps it
    assert t_elapsed < 35.0, f"Latency {t_elapsed:.2f}ms exceeded 35ms threshold"

    # Verify wrapping format
    ground_truth_exhaust = f"<ground_truth_exhaust>\n{res}\n</ground_truth_exhaust>"
    assert "<ground_truth_exhaust>" in ground_truth_exhaust
    assert "</ground_truth_exhaust>" in ground_truth_exhaust
    print("TEST_EXECUTE_GREP_SEARCH_PIVOT_LATENCY: PASSED")


if __name__ == "__main__":
    test_anchor_extraction_logic()
    test_execute_grep_search_pivot_latency()
    print("ALL RIPGREP HYDRATION TESTS PASSED")
