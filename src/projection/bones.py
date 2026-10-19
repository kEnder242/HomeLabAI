#!/usr/bin/env python3
"""
[DEPRECATION NOTICE - SPR-107.0 / FEAT-665]
projection.bones is superseded by projection.ast_reconciliation.
All AST reconciliation, SpineManager, and diff algorithms have been re-anchored to:
    HomeLabAI/src/projection/ast_reconciliation.py

This module provides 100% backwards-compatible alias re-exports.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "projection.bones has been superseded by projection.ast_reconciliation (SPR-107.0). "
    "Please update your imports to 'from projection.ast_reconciliation import ...'",
    DeprecationWarning,
    stacklevel=2,
)

from projection.ast_reconciliation import (
    BONE_SCHEMA_VERSION,
    SPINE_SCHEMA_VERSION,
    DocumentAST,
    DocumentNode,
    SpineManager,
    extract_bones,
    normalize_ast,
    reconcile_diff,
)

__all__ = [
    "BONE_SCHEMA_VERSION",
    "SPINE_SCHEMA_VERSION",
    "DocumentAST",
    "DocumentNode",
    "SpineManager",
    "extract_bones",
    "normalize_ast",
    "reconcile_diff",
]
