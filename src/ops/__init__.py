# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
"""[FEAT-620] Ops Execution Engine — Deterministic operational action runner."""

from .ops_runner import OpsRunner, execute_op

__all__ = ["OpsRunner", "execute_op"]
