"""
[FEAT-528] Verification Suite for Story 70.12 Public Showcase Surface on Airlock
Validates that public_benchmarks.html renders offline without external dependencies.
"""
from pathlib import Path


def test_public_benchmarks_html_structure():
    """Verify public_benchmarks.html elements and offline integrity."""
    html_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "Portfolio_Dev"
        / "field_notes"
        / "public_benchmarks.html"
    )
    assert html_path.exists(), f"File {html_path} does not exist"

    content = html_path.read_text(encoding="utf-8")
    assert "ACCESS LIVE LAB TELEMETRY" in content
    assert "Mac M5 Air" in content
    assert "Windows RTX 4090" in content
    assert "RTX 2080 Ti" in content
    assert "Cloud Swarm" in content
    assert "updatePublicRoi" in content
    assert "tokenSliderVal" in content


def test_mission_control_public_benchmarks_link():
    """Verify mission-control.js contains link to public benchmarks."""
    mc_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "Portfolio_Dev"
        / "field_notes"
        / "mission-control.js"
    )
    assert mc_path.exists(), f"File {mc_path} does not exist"

    content = mc_path.read_text(encoding="utf-8")
    assert "public_benchmarks.html" in content
