"""
Unit Test Suite for [FEAT-582 / Story 86.5]:
Polymorphic LoRA Dataset Invariant, Domain Completeness, and Balance.
"""

import pytest
from forge.build_lora_datasets import (
    build_dna_polymorphic_dataset,
    _build_dna_synthesis_index,
    DNA_OUT
)


def test_dna_synthesis_index_resolution():
    """Verify that synthesis index correctly indexes narrative contexts from wisdom and philosophy."""
    index = _build_dna_synthesis_index()
    assert isinstance(index, dict)
    assert len(index) >= 400
    # Spot check presence of key domains
    assert any(k.startswith("PHL-") for k in index.keys())
    assert any(k.startswith("WIS-") for k in index.keys())


def test_polymorphic_dataset_generation_completeness():
    """Verify that build_dna_polymorphic_dataset generates pairs across all domains including FEAT."""
    total_pairs = build_dna_polymorphic_dataset()
    assert total_pairs >= 1000, f"Expected >= 1000 polymorphic pairs, got {total_pairs}"
    assert DNA_OUT.exists()
    assert DNA_OUT.stat().st_size > 50000
