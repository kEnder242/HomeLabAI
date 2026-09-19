#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_paper_engine.py
[Sprint 84 / Sprint 85 Validation Suite - BKM-024]
Tests for the Lens Crafter, Paper Grading Engine, Citation Expander, and Synapse Graph.
"""

import os
import json
import pytest
from pathlib import Path

# Paths
CUR_DIR = Path(__file__).resolve().parent
SRC_DIR = CUR_DIR.parent
WORKSPACE_DIR = SRC_DIR.parent.parent / "Portfolio_Dev"


def test_craft_lens():
    """Test compiling rubric from unstructured text/advice."""
    from curator.lens_service import craft_lens
    
    advice = """
    - Make every bullet quantifiable.
    - Cut all fluff and ensure each point begins with a powerful active verb.
    - Tie experiences directly to systems architecture and performance.
    """
    res = craft_lens(
        lens_id="test_recruiter_lens",
        content=advice,
        title="Test Recruiter Lens",
        persona={
            "name": "Senior Talent Partner",
            "role": "Principal Recruiter",
            "lens_perspective": "Pragmatic hiring manager"
        }
    )
    assert res.get("status") == "success"
    rubric = res.get("rubric")
    assert rubric is not None
    assert rubric.get("lens_id") == "test_recruiter_lens"
    assert len(rubric.get("rules", [])) >= 3
    assert rubric.get("persona", {}).get("name") == "Senior Talent Partner"


def test_grade_paper_ast():
    """Test AST grading engine against sample paper AST."""
    from curator.lens_service import grade_paper
    
    # Run grading on PAPER-RESUME
    res = grade_paper(
        paper_id="PAPER-RESUME",
        revision_id="v1_baseline",
        lens_id="farah_sharghi_recruiter_v1"
    )
    assert res.get("status") == "success"
    assert res.get("total_flags_generated", 0) > 0
    graded_ast = res.get("graded_ast")
    assert graded_ast is not None
    
    # Check that flags were attached to nodes
    all_flags = []
    for sec in graded_ast.get("sections", []):
        for node in sec.get("nodes", []):
            all_flags.extend(node.get("review_flags", []))
    assert len(all_flags) > 0
    categories = {f.get("category") for f in all_flags}
    assert "PROSE" in categories or "REFINEMENT" in categories


def test_expand_citations():
    """Test research and citation discovery expansion."""
    from curator.lens_service import expand_citations
    
    res = expand_citations(
        topic="Pre-silicon shift-left validation and hardware emulation",
        top_k=3
    )
    assert res.get("status") == "success"
    suggestions = res.get("suggestions", [])
    assert len(suggestions) > 0
    for s in suggestions:
        assert "id" in s
        assert "title" in s
        assert "source" in s


def test_dna_connections_graph():
    """Test DNA Synapse Graph compilation across all polymorphic domains."""
    import sys
    sys.path.insert(0, str(WORKSPACE_DIR / "scripts"))
    from generate_connections_graph import compile_connections_graph
    
    graph = compile_connections_graph()
    assert graph.get("status") == "ok"
    assert graph.get("total_nodes", 0) > 100
    assert graph.get("total_links", 0) > 50
    assert "census" in graph
    
    # Check domain coverage
    census = graph["census"]
    for d in ["PHL", "WIS", "BKM", "FEAT"]:
        assert d in census
