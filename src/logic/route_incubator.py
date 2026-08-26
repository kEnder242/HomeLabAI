"""
[FEAT-472] Dynamic Route Incubation Sandbox

Pure, decoupled module that manages mouse-defined candidate routes in
``config/triage_supplement.json``.  Routes incubate here before promotion
to core ``triage_policy.json``.

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

_MOUSE_DEF_PREFIX: str = "MOUSE_DEF:"

_TRAVERSAL_MODES: frozenset[str] = frozenset({"TOPIC_FIRST", "TIME_FIRST", "STREAM_REPLAY"})

_REQUIRED_CANDIDATE_FIELDS: frozenset[str] = frozenset({
    "intent",
    "target_domain",
    "enabled",
    "creator",
    "created_at",
    "hit_count",
    "success_count",
    "last_used",
    "feedback_log",
})

_OPTIONAL_CANDIDATE_FIELDS: frozenset[str] = frozenset({
    "traversal_mode",
    "rag_config",
})


class RouteIncubatorError(Exception):
    """Raised when the supplement file is missing, malformed, or schema-invalid."""


class RouteIncubator:
    """Manages candidate routes in the Tier-2 mouse sandbox.

    Routes are persisted to ``config/triage_supplement.json`` and are
    automatically prefixed with ``MOUSE_DEF:`` if not already present.
    Supports registration, hit tracking, export for solidification, and
    retirement.

    Parameters
    ----------
    supplement_path:
        Absolute or relative path to the triage supplement JSON file.
        Defaults to ``config/triage_supplement.json`` relative to the caller.
    """

    _DEFAULT_RELATIVE_PATH: str = "config/triage_supplement.json"

    def __init__(self, supplement_path: str | Path | None = None) -> None:
        if supplement_path is not None:
            self._supplement_path: Path = Path(supplement_path)
        else:
            self._supplement_path = Path(self._DEFAULT_RELATIVE_PATH)

        self._candidates: dict[str, Any] = {}
        self._last_mtime: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────

    def load_supplement(self, path: str | Path | None = None) -> dict[str, Any]:
        """Load and cache the supplement from disk.

        Parameters
        ----------
        path:
            Optional override path for this load operation.

        Returns
        -------
        The supplement dict (``{"candidates": {...}}``).

        Raises
        ------
        RouteIncubatorError
            If the file is missing, contains invalid JSON, or fails schema
            validation.
        """
        target = Path(path) if path is not None else self._supplement_path

        if not target.exists():
            raise RouteIncubatorError(
                f"Supplement file not found: {target}"
            )

        try:
            raw = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise RouteIncubatorError(
                f"Failed to read supplement file {target}: {exc}"
            ) from exc

        try:
            supplement = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RouteIncubatorError(
                f"Invalid JSON in supplement file {target}: {exc}"
            ) from exc

        errors = self.validate_supplement_schema(supplement)
        if errors:
            raise RouteIncubatorError(
                f"Schema validation failed for {target}: {'; '.join(errors)}"
            )

        self._candidates = supplement.get("candidates", {})
        self._last_mtime = target.stat().st_mtime
        self._supplement_path = target

        logger.info("Triage supplement loaded from %s", target)
        return supplement

    def register_candidate_route(
        self,
        vibe_name: str,
        intent: str,
        target_domain: str,
        traversal_mode: str | None = None,
        creator: str = "Brain",
        rag_config: dict[str, Any] | None = None,
    ) -> str:
        """Register a new candidate route in the sandbox.

        Parameters
        ----------
        vibe_name:
            Base name for the route (auto-prefixed with ``MOUSE_DEF:``).
        intent:
            Human-readable intent description.
        target_domain:
            Target retrieval domain (e.g. ``"dream_stream"``,
            ``"exp_bkm"``).
        traversal_mode:
            Optional traversal mode.  Must be one of ``TOPIC_FIRST``,
            ``TIME_FIRST``, or ``STREAM_REPLAY`` if provided.
        creator:
            Entity that created the route (default ``"Brain"``).
        rag_config:
            Optional RAG configuration dict.

        Returns
        -------
        The fully-qualified route name (with ``MOUSE_DEF:`` prefix).

        Raises
        ------
        RouteIncubatorError
            If the route already exists or the traversal mode is invalid.
        """
        if traversal_mode is not None and traversal_mode not in _TRAVERSAL_MODES:
            raise RouteIncubatorError(
                f"Invalid traversal_mode '{traversal_mode}'. "
                f"Must be one of {sorted(_TRAVERSAL_MODES)}"
            )

        # Auto-prefix with MOUSE_DEF: if not present
        full_name = vibe_name if vibe_name.startswith(_MOUSE_DEF_PREFIX) else f"{_MOUSE_DEF_PREFIX}{vibe_name}"

        if full_name in self._candidates:
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' already exists. "
                f"Use record_route_hit to update, or retire first."
            )

        now = time.time()
        candidate: dict[str, Any] = {
            "intent": intent,
            "target_domain": target_domain,
            "enabled": True,
            "creator": creator,
            "created_at": now,
            "hit_count": 0,
            "success_count": 0,
            "last_used": 0.0,
            "feedback_log": [],
        }

        if traversal_mode is not None:
            candidate["traversal_mode"] = traversal_mode

        if rag_config is not None:
            candidate["rag_config"] = rag_config

        self._candidates[full_name] = candidate
        self._persist()

        logger.info("Registered candidate route: %s", full_name)
        return full_name

    def record_route_hit(
        self,
        vibe_name: str,
        success: bool,
        feedback: str = "",
    ) -> None:
        """Record a hit against a candidate route.

        Parameters
        ----------
        vibe_name:
            Route name (with or without ``MOUSE_DEF:`` prefix).
        success:
            Whether the route produced a successful result.
        feedback:
            Optional human feedback string.

        Raises
        ------
        RouteIncubatorError
            If the route does not exist or is retired.
        """
        full_name = self._resolve_name(vibe_name)

        if full_name not in self._candidates:
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' not found."
            )

        candidate = self._candidates[full_name]

        if not candidate.get("enabled", True):
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' is retired (disabled)."
            )

        candidate["hit_count"] = candidate.get("hit_count", 0) + 1
        if success:
            candidate["success_count"] = candidate.get("success_count", 0) + 1
        candidate["last_used"] = time.time()

        if feedback:
            candidate.setdefault("feedback_log", []).append({
                "timestamp": time.time(),
                "success": success,
                "feedback": feedback,
            })

        self._persist()
        logger.info(
            "Recorded hit for %s (success=%s, hits=%d)",
            full_name,
            success,
            candidate["hit_count"],
        )

    def get_candidate_routes(self, active_only: bool = True) -> dict[str, Any]:
        """Retrieve candidate routes from the sandbox.

        Parameters
        ----------
        active_only:
            If ``True`` (default), return only enabled routes.

        Returns
        -------
        A dict mapping route names to their config dicts.
        """
        if active_only:
            return {
                name: cfg
                for name, cfg in self._candidates.items()
                if cfg.get("enabled", True)
            }
        return dict(self._candidates)

    def export_for_solidification(self, vibe_name: str) -> dict[str, Any]:
        """Format a candidate route for promotion to core triage_policy.json.

        Parameters
        ----------
        vibe_name:
            Route name (with or without ``MOUSE_DEF:`` prefix).

        Returns
        -------
        A dict matching the triage_policy.json vibe rule schema.

        Raises
        ------
        RouteIncubatorError
            If the route does not exist or is retired.
        """
        full_name = self._resolve_name(vibe_name)

        if full_name not in self._candidates:
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' not found."
            )

        candidate = self._candidates[full_name]

        if not candidate.get("enabled", True):
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' is retired (disabled)."
            )

        # Build the export dict matching triage_policy.json vibe schema
        export: dict[str, Any] = {
            "description": candidate.get("intent", ""),
            "enabled": True,
            "default_domain": candidate["target_domain"],
        }

        # Add RAG config if present
        rag_config = candidate.get("rag_config")
        if rag_config is not None:
            export["rag"] = rag_config
        elif candidate.get("traversal_mode") is not None:
            # Synthesize RAG from traversal_mode + target_domain
            export["rag"] = {
                "target_domain": candidate["target_domain"],
                "traversal": candidate["traversal_mode"],
                "allowed_collections": [],
                "max_distance": 0.75,
            }
        else:
            export["rag"] = None

        # Attach incubation metadata
        export["_incubation"] = {
            "source": full_name,
            "creator": candidate.get("creator", "Brain"),
            "hit_count": candidate.get("hit_count", 0),
            "success_count": candidate.get("success_count", 0),
            "created_at": candidate.get("created_at", 0.0),
        }

        return export

    def retire_candidate_route(self, vibe_name: str) -> None:
        """Mark a candidate route as retired (disabled).

        Parameters
        ----------
        vibe_name:
            Route name (with or without ``MOUSE_DEF:`` prefix).

        Raises
        ------
        RouteIncubatorError
            If the route does not exist.
        """
        full_name = self._resolve_name(vibe_name)

        if full_name not in self._candidates:
            raise RouteIncubatorError(
                f"Candidate route '{full_name}' not found."
            )

        self._candidates[full_name]["enabled"] = False
        self._persist()

        logger.info("Retired candidate route: %s", full_name)

    def validate_supplement_schema(self, supplement: Any) -> list[str]:
        """Validate a supplement dict against the expected schema.

        Parameters
        ----------
        supplement:
            The parsed JSON supplement dict.

        Returns
        -------
        A list of human-readable error strings.  Empty list means valid.
        """
        errors: list[str] = []

        if not isinstance(supplement, dict):
            return ["Supplement root must be a JSON object"]

        candidates = supplement.get("candidates")
        if not isinstance(candidates, dict):
            errors.append("Missing or non-dict 'candidates' key")
            return errors

        for name, cfg in candidates.items():
            if not isinstance(cfg, dict):
                errors.append(f"Candidate '{name}' must be a JSON object")
                continue

            # Required fields
            for field in _REQUIRED_CANDIDATE_FIELDS:
                if field not in cfg:
                    errors.append(f"Candidate '{name}' missing required field '{field}'")

            # enabled must be bool
            if "enabled" in cfg and not isinstance(cfg["enabled"], bool):
                errors.append(f"Candidate '{name}' 'enabled' must be boolean")

            # hit_count must be non-negative int
            hit_count = cfg.get("hit_count")
            if hit_count is not None:
                if not isinstance(hit_count, int) or hit_count < 0:
                    errors.append(f"Candidate '{name}' 'hit_count' must be a non-negative integer")

            # success_count must be non-negative int
            success_count = cfg.get("success_count")
            if success_count is not None:
                if not isinstance(success_count, int) or success_count < 0:
                    errors.append(f"Candidate '{name}' 'success_count' must be a non-negative integer")

            # traversal_mode validation (optional)
            traversal = cfg.get("traversal_mode")
            if traversal is not None and traversal not in _TRAVERSAL_MODES:
                errors.append(
                    f"Candidate '{name}' 'traversal_mode' must be one of "
                    f"{sorted(_TRAVERSAL_MODES)}, got '{traversal}'"
                )

            # rag_config validation (optional)
            rag = cfg.get("rag_config")
            if rag is not None and not isinstance(rag, dict):
                errors.append(f"Candidate '{name}' 'rag_config' must be a JSON object or null")

        return errors

    # ── Internal Helpers ───────────────────────────────────────────────────

    def _resolve_name(self, vibe_name: str) -> str:
        """Resolve a vibe name to its fully-qualified MOUSE_DEF: form."""
        return (
            vibe_name
            if vibe_name.startswith(_MOUSE_DEF_PREFIX)
            else f"{_MOUSE_DEF_PREFIX}{vibe_name}"
        )

    def _persist(self) -> None:
        """Atomically write the current candidates to disk.

        Uses .tmp + replace pattern for crash safety (BKM-015 Class 1).
        """
        supplement: dict[str, Any] = {
            "_schema_version": "1.0.0",
            "_description": (
                "Dynamic Route Incubation Sandbox – mouse-defined candidate "
                "routes. Routes are prefixed with MOUSE_DEF: and incubated "
                "here before promotion to core triage_policy.json."
            ),
            "candidates": self._candidates,
        }

        tmp_path = self._supplement_path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(
                json.dumps(supplement, indent=4, sort_keys=True),
                encoding="utf-8",
            )
            tmp_path.replace(self._supplement_path)
            self._last_mtime = self._supplement_path.stat().st_mtime
        except OSError as exc:
            logger.error("Failed to persist supplement: %s", exc)
            raise RouteIncubatorError(
                f"Failed to persist supplement to {self._supplement_path}: {exc}"
            ) from exc
