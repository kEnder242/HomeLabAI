#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_dna_roundtrip_consistency.py
[FEAT-604 / BKM-024 / ADR-008]

Bi-Directional File-to-DB Round-Trip Consistency & Invariant Verification Suite.
Asserts mathematical identity:
  Delta(Original Source, Reconstruct(Bone Collection, R1)) == 0
"""

import sys
from pathlib import Path

HOME_DIR = Path(__file__).resolve().parent.parent.parent
LAB_ROOT = HOME_DIR.parent
PORTFOLIO_DIR = LAB_ROOT / "Portfolio_Dev"
SCRIPTS_DIR = PORTFOLIO_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(HOME_DIR / "src"))

from dna_macro_compiler import (
    parse_macro_string,
    parse_markdown_with_dna_macros,
    reconstruct_source_from_bones,
    compile_paper_to_markdown
)


def test_dna_macro_parsing_and_serialization():
    """Test inline DNA macro parsing, attribute extraction, and comment serialization."""
    comment = "<!-- [WIS-482:R2 style=paragraph lens=ActiveVoice extra=123] -->"
    macro = parse_macro_string(comment)
    assert macro is not None
    assert macro.card_id == "WIS-482"
    assert macro.revision == "R2"
    assert macro.style == "paragraph"
    assert macro.lens == "ActiveVoice"
    assert macro.extra_attrs.get("extra") == "123"

    reserialized = macro.to_macro_comment()
    assert "WIS-482:R2" in reserialized
    assert "style=paragraph" in reserialized
    assert "lens=ActiveVoice" in reserialized


def test_markdown_with_dna_macros_parsing():
    """Test parsing a full markdown document with embedded DNA macros into structured vertebrae."""
    doc = """
# Test Document Header

<!-- [WIS-482:R1 style=paragraph] -->
When using agents to code, long context becomes a problem.

<!-- [FEAT-600:R1 style=bullet] -->
* Local models hold offline data primacy.
"""
    chunks = parse_markdown_with_dna_macros(doc)
    assert len(chunks) == 3
    assert chunks[0]["macro"] is None
    assert "Test Document Header" in chunks[0]["text"]
    assert chunks[1]["macro"]["id"] == "WIS-482"
    assert chunks[1]["macro"]["revision"] == "R1"
    assert "When using agents to code" in chunks[1]["text"]
    assert chunks[2]["macro"]["id"] == "FEAT-600"
    assert "Local models hold offline" in chunks[2]["text"]


def test_words_first_inline_citation_parsing():
    """
    Test words-first inline citation grammar:
    "I walked the dog" [PHL-231] R1 style=Heading
    """
    doc = """
# Dog Paper

"I walked the dog" [PHL-231] R1 style=Heading

It was a crisp morning with cold fog rolling over the grass. [WIS-102] R1
"""
    chunks = parse_markdown_with_dna_macros(doc)
    assert len(chunks) == 3
    assert "Dog Paper" in chunks[0]["text"]
    assert chunks[1]["text"] == "I walked the dog"
    assert chunks[1]["macro"]["id"] == "PHL-231"
    assert chunks[1]["macro"]["revision"] == "R1"
    assert chunks[1]["macro"]["style"] == "heading"

    assert "It was a crisp morning" in chunks[2]["text"]
    assert chunks[2]["macro"]["id"] == "WIS-102"
    assert chunks[2]["macro"]["revision"] == "R1"



def test_bone_collection_roundtrip_exact_identity():
    """
    [FEAT-604 Invariant]
    Verify that reconstructing a document from its 1:1 Bone Collection using R1
    produces exact, character-for-character identity with the source verbatim paragraphs.
    """
    bone_scratchpad = {
        "id": "bone_test_roundtrip",
        "name": "Test Roundtrip Document",
        "bones": [
            {
                "sequence": 1,
                "id": "WIS-001",
                "origin_verbatim": "Paragraph 1 verbatim source text.",
                "revisions": [
                    {"version": 1, "lens": "Original Verbatim", "text": "Paragraph 1 verbatim source text."},
                    {"version": 2, "lens": "Author Polished", "text": "Paragraph 1 polished text."}
                ]
            },
            {
                "sequence": 2,
                "id": "PHL-001",
                "origin_verbatim": "Paragraph 2 verbatim source text with numbers 123.",
                "revisions": [
                    {"version": 1, "lens": "Original Verbatim", "text": "Paragraph 2 verbatim source text with numbers 123."}
                ]
            },
            {
                "sequence": 3,
                "id": "FEAT-001",
                "origin_verbatim": "Paragraph 3 final conclusion.",
                "revisions": [
                    {"version": 1, "lens": "Original Verbatim", "text": "Paragraph 3 final conclusion."}
                ]
            }
        ]
    }

    expected_original = (
        "Paragraph 1 verbatim source text.\n\n"
        "Paragraph 2 verbatim source text with numbers 123.\n\n"
        "Paragraph 3 final conclusion."
    )

    reconstructed = reconstruct_source_from_bones(bone_scratchpad, revision_lens="Original Verbatim")
    assert reconstructed == expected_original, "Invariant broken: Reconstructed R1 does not match original source!"


def test_multi_collection_paper_compilation_and_reprojection():
    """
    [FEAT-603]
    Verify composing a paper across multiple bone collections and re-projecting through lenses.
    """
    col_a = {
        "name": "Section A",
        "bones": [
            {
                "sequence": 1,
                "id": "WIS-482",
                "origin_verbatim": "Raw text A.",
                "revisions": [
                    {"version": 1, "lens": "Academic", "text": "Academic citation text A."}
                ],
                "mutations": [
                    {"id": "mut_exec", "lens": "Executive", "text": "Executive impact bullet A."}
                ]
            }
        ]
    }

    col_b = {
        "name": "Section B",
        "bones": [
            {
                "sequence": 1,
                "id": "FEAT-600",
                "origin_verbatim": "Raw text B.",
                "revisions": [
                    {"version": 1, "lens": "Academic", "text": "Academic citation text B."}
                ],
                "mutations": [
                    {"id": "mut_exec", "lens": "Executive", "text": "Executive impact bullet B."}
                ]
            }
        ]
    }

    # 1. Project under Academic lens
    paper_academic = compile_paper_to_markdown([col_a, col_b], lens="Academic")
    assert "Academic citation text A." in paper_academic
    assert "Academic citation text B." in paper_academic
    assert "<!-- [WIS-482:R1" in paper_academic

    # 2. Re-project under Executive lens
    paper_executive = compile_paper_to_markdown([col_a, col_b], lens="Executive")
    assert "Executive impact bullet A." in paper_executive
    assert "Executive impact bullet B." in paper_executive
    assert "<!-- [WIS-482:MUT_EXEC" in paper_executive
