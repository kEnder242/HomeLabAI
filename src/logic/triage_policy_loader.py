"""
[FEAT-467] Declarative Triage Policy Loader

Pure, stateless module that loads and validates the triage policy from
``config/triage_policy.json``.  Provides hot-reload on file modification,
vibe-rule lookup, and schema validation — all decoupled from the TriageEngine
and CognitiveHub.

BKM-015 Compliant: zero third-party dependencies beyond the Python standard library.
Class 1 Design: no test-framework imports in production code.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Schema Constants ──────────────────────────────────────────────────────

_TRAVERSAL_MODES: frozenset[str] = frozenset({"TOPIC_FIRST", "TIME_FIRST", "STREAM_REPLAY"})

_REQUIRED_VIBE_FIELDS: frozenset[str] = frozenset({"description", "enabled", "default_domain"})

_OPTIONAL_RAG_FIELDS: frozenset[str] = frozenset({
    "target_domain",
    "traversal",
    "allowed_collections",
    "max_distance",
})

_OPTIONAL_VIBE_FIELDS: frozenset[str] = frozenset({
    "importance",
    "examples",
})


class TriagePolicyError(Exception):
    """Raised when the policy file is missing, malformed, or schema-invalid."""


class TriagePolicyLoader:
    """Loads, validates, and serves the declarative triage policy.

    The loader reads a JSON policy file, validates its schema, caches the
    parsed result, and supports hot-reload when the file's mtime changes.
    All methods are synchronous and safe to call from any context.

    Parameters
    ----------
    policy_path:
        Absolute or relative path to the triage policy JSON file.
        Defaults to ``config/triage_policy.json`` relative to the caller.
    """

    _DEFAULT_RELATIVE_PATH: str = "config/triage_policy.json"

    def __init__(self, policy_path: str | Path | None = None) -> None:
        self._explicit_path = policy_path is not None
        if policy_path is not None:
            self._policy_path: Path = Path(policy_path)
        else:
            rel = Path(self._DEFAULT_RELATIVE_PATH)
            if not rel.exists():
                fallback = Path(__file__).resolve().parent.parent.parent / self._DEFAULT_RELATIVE_PATH
                if fallback.exists():
                    rel = fallback
            self._policy_path = rel

        self._policy: dict[str, Any] | None = None
        self._last_mtime: float = 0.0
        self._last_load_time: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────

    def load_policy(self, path: str | Path | None = None) -> dict[str, Any]:
        """Load and cache the triage policy from disk.

        If *path* is provided, it overrides the instance's default path for
        this single call.  The loaded policy is validated via
        :meth:`validate_policy_schema` before caching.

        Parameters
        ----------
        path:
            Optional override path for this load operation.

        Returns
        -------
        The validated policy dict.

        Raises
        ------
        TriagePolicyError
            If the file is missing, contains invalid JSON, or fails schema
            validation.
        """
        target = Path(path) if path is not None else self._policy_path

        if not target.exists():
            raise TriagePolicyError(f"Triage policy file not found: {target}")

        try:
            with open(target, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            raise TriagePolicyError(f"Invalid JSON in {target}: {exc}") from exc
        except OSError as exc:
            raise TriagePolicyError(f"Cannot read {target}: {exc}") from exc

        errors = self.validate_policy_schema(raw)
        if errors:
            raise TriagePolicyError(
                f"Schema validation failed for {target}:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        policy = raw
        self._policy = policy
        self._last_mtime = target.stat().st_mtime
        self._last_load_time = time.monotonic()
        self._policy_path = target

        logger.info("Triage policy loaded from %s", target)
        return policy

    def get_vibe_rule(self, vibe: str) -> dict[str, Any] | None:
        """Retrieve the rule dict for a specific vibe."""
        if self._policy is None and not self._explicit_path:
            try:
                self.load_policy()
            except Exception:
                return None

        if self._policy is None:
            return None

        vibes = self._policy.get("vibes", {})
        return vibes.get(vibe.upper())

    def get_active_vibes(self) -> list[str]:
        """Return sorted list of enabled vibe names."""
        if self._policy is None and not self._explicit_path:
            try:
                self.load_policy()
            except Exception:
                return []

        if self._policy is None:
            return []

        vibes = self._policy.get("vibes", {})
        return sorted(
            name for name, rule in vibes.items()
            if isinstance(rule, dict) and rule.get("enabled", False)
        )

    def get_rag_config(self, vibe: str) -> dict[str, Any] | None:
        """Retrieve the RAG configuration for a vibe, if any.

        Conversational and supervisory vibes omit the ``"rag"`` key entirely,
        which returns ``None``.  Retrieval vibes return the full RAG dict.

        Parameters
        ----------
        vibe:
            Case-insensitive vibe name.

        Returns
        -------
        The RAG config dict, or ``None`` when RAG is omitted/disabled.
        """
        rule = self.get_vibe_rule(vibe)
        if rule is None:
            return None
        return rule.get("rag")

    def validate_policy_schema(self, policy: dict[str, Any]) -> list[str]:
        """Validate a policy dict against the expected schema.

        Parameters
        ----------
        policy:
            The parsed JSON policy dict.

        Returns
        -------
        A list of human-readable error strings.  Empty list means valid.
        """
        errors: list[str] = []

        if not isinstance(policy, dict):
            return ["Policy root must be a JSON object"]

        vibes = policy.get("vibes")
        if not isinstance(vibes, dict):
            errors.append("Missing or non-dict 'vibes' key")
            return errors

        for name, rule in vibes.items():
            if not isinstance(rule, dict):
                errors.append(f"Vibe '{name}' must be a JSON object")
                continue

            # Required fields
            for field in _REQUIRED_VIBE_FIELDS:
                if field not in rule:
                    errors.append(f"Vibe '{name}' missing required field '{field}'")

            # enabled must be bool
            if "enabled" in rule and not isinstance(rule["enabled"], bool):
                errors.append(f"Vibe '{name}' 'enabled' must be boolean")

            # RAG validation (optional)
            rag = rule.get("rag")
            if rag is not None:
                if not isinstance(rag, dict):
                    errors.append(f"Vibe '{name}' 'rag' must be a JSON object or null")
                    continue

                traversal = rag.get("traversal")
                if traversal is not None and traversal not in _TRAVERSAL_MODES:
                    errors.append(
                        f"Vibe '{name}' 'rag.traversal' must be one of "
                        f"{sorted(_TRAVERSAL_MODES)}, got '{traversal}'"
                    )

                allowed = rag.get("allowed_collections")
                if allowed is not None and not isinstance(allowed, list):
                    errors.append(f"Vibe '{name}' 'rag.allowed_collections' must be a list")

                max_dist = rag.get("max_distance")
                if max_dist is not None:
                    if not isinstance(max_dist, (int, float)):
                        errors.append(
                            f"Vibe '{name}' 'rag.max_distance' must be numeric"
                        )
                    elif not (0.0 <= float(max_dist) <= 1.0):
                        errors.append(
                            f"Vibe '{name}' 'rag.max_distance' must be in [0.0, 1.0]"
                        )

        return errors

    def hot_reload_if_modified(self) -> bool:
        """Check file mtime and reload if changed since last load.

        Returns
        -------
        ``True`` if the policy was reloaded (file changed), ``False`` if
        unchanged or if no policy has been loaded yet.
        """
        if self._policy is None:
            return False

        if not self._policy_path.exists():
            logger.warning(
                "Hot-reload skipped: policy file disappeared: %s",
                self._policy_path,
            )
            return False

        current_mtime = self._policy_path.stat().st_mtime
        if current_mtime <= self._last_mtime:
            return False

        try:
            self.load_policy()
            logger.info(
                "Hot-reloaded triage policy (mtime %.3f -> %.3f)",
                self._last_mtime,
                current_mtime,
            )
            return True
        except TriagePolicyError as exc:
            logger.error("Hot-reload failed: %s", exc)
            return False
