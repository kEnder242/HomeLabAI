"""[FEAT-620] Ops Execution Engine — Deterministic operational action runner."""

from .ops_runner import OpsRunner, execute_op

__all__ = ["OpsRunner", "execute_op"]
