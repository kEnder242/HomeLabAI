"""
Projection Engine Package
[FEAT-603 / FEAT-594 / FEAT-601 / FEAT-622 / WIS-487]

Consolidated projection lifecycle for the Federated Lab. A single Python API
callable by both the CLI and the web endpoints.

Module map:
  * :mod:`projection.bones`       -- DocumentAST / DocumentNode, bone extraction
                                    (pi(C) re-anchoring), reconciliation diff.
  * :mod:`projection.lenses`      -- lens compiler (``UNSAFE_TO_CRAFT`` refusal
                                    branch), rule schema validator, symbolic
                                    rubric detectors and the tier_0/tier_1 split.
  * :mod:`projection.engine`      -- ProjectionEngine: bind lens to bones,
                                    adjudicate, reconcile, emit drift metrics.
  * :mod:`projection.recommender` -- topic alignment matrix, triage router,
                                    mutation proposals, grounded cover letters.

Usage::

    from projection import ProjectionEngine, craft_lens, extract_bones

    lens = craft_lens("farah_sharghi_recruiter_v1", "Ex-Google Recruiter Playbook")
    if lens["status"] == "success":
        result = ProjectionEngine().project(document_ast, lens)
        print(result["total_review_flags"], result["drift"]["flagged_ratio"])

Architectural mandates: BKM-070 (re-anchoring law), BKM-015 (parsing and
evaluation taxonomy), WIS-487 (total function compilation), BKM-046 (fast-path
retrieval). Hermetic by default -- no filesystem, network or LLM dependency in
the core import path.
"""

from .bones import DocumentAST, DocumentNode, extract_bones, reconcile_diff
from .engine import ProjectionEngine
from .lenses import POWER_VERBS, WEAK_OPENINGS, craft_lens, validate_lens_schema
from .recommender import RecommendationRouter, TopicAlignmentMatrix

__version__ = "2.0.0"

__all__ = [
    # bones
    "DocumentNode",
    "DocumentAST",
    "extract_bones",
    "reconcile_diff",
    # lenses
    "craft_lens",
    "validate_lens_schema",
    "POWER_VERBS",
    "WEAK_OPENINGS",
    # engine
    "ProjectionEngine",
    # recommender
    "TopicAlignmentMatrix",
    "RecommendationRouter",
]
