"""
Override Parser Satellite (FEAT-145/REF-01).

Extracts and encapsulates GEM-xxxx / BKM-xxx override detection, parsing,
and atomic persistence from CognitiveHub.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 1. Query Detection
# ---------------------------------------------------------------------------

_PREFIX_RE = re.compile(r"^\s*\[(?:ME|USER)\]\s*", re.IGNORECASE)
_GEM_BKM_RE = re.compile(r"\b((?:GEM|BKM)-\d{3,4})\b")
_CORRECTION_KEYWORDS = frozenset(
    {"correct", "wrong", "fix", "override", "change", "update"}
)


def is_override_query(turn: str) -> tuple[bool, Optional[str]]:
    """Detect whether *turn* carries an override intent.

    Steps:
      1. Strip client transcript prefixes ``[ME]`` or ``[USER]``.
      2. Search for a GEM-xxxx / BKM-xxx identifier.
      3. Verify the presence of at least one correction-intent keyword.

    Returns
    -------
    (True, gem_id) when the turn is an override query, (False, None) otherwise.
    """
    stripped = _PREFIX_RE.sub("", turn)

    m = _GEM_BKM_RE.search(stripped)
    if m is None:
        return False, None

    gem_id: str = m.group(1)

    # Tokenise on non-alpha characters so "correction" matches "correct".
    tokens = set(re.findall(r"[a-z]+", stripped.lower()))
    if not _CORRECTION_KEYWORDS & tokens:
        return False, None

    return True, gem_id


# ---------------------------------------------------------------------------
# 2. Resident Parsing (async)
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = (
    "You are a structured-data extraction assistant.\n"
    "Given the user instruction below, extract an update object with the keys: "
    "rank (int|None), title (str|None), synopsis (str|None), domain (str|None).\n"
    "Return ONLY a JSON object — no markdown fences, no commentary.\n\n"
    "User instruction: {turn}"
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def parse_override_with_resident(
    gem_id: str,
    turn: str,
    resident_caller: Any,
) -> Optional[dict]:
    """Ask the *resident* LLM to extract structured updates from *turn*.

    Parameters
    ----------
    gem_id:
        The identifier being overridden (e.g. ``GEM-0142``).
    turn:
        The raw user utterance.
    resident_caller:
        An async callable ``await resident_caller(prompt) -> str`` that
        forwards the prompt to the resident model and returns its text
        response.

    Returns
    -------
    A dict with keys ``rank``, ``title``, ``synopsis``, ``domain`` (values
    may be ``None``), or ``None`` on parse failure.
    """
    prompt = _EXTRACTION_PROMPT.format(turn=turn)

    try:
        if hasattr(resident_caller, "think") and callable(resident_caller.think):
            raw = await resident_caller.think(prompt, internal=True)
        elif hasattr(resident_caller, "call_tool") and callable(resident_caller.call_tool):
            res = await resident_caller.call_tool("think", {"prompt": prompt, "query": prompt})
            if hasattr(res, "content") and res.content:
                raw = res.content[0].text
            else:
                raw = str(res)
        elif callable(resident_caller):
            raw = await resident_caller(prompt)
        else:
            return None
    except Exception:  # noqa: BLE001 – resident failures must not propagate
        return None

    if not isinstance(raw, str):
        return None

    m = _JSON_RE.search(raw)
    if m is None:
        return None

    try:
        parsed: dict = json.loads(m.group(0))
    except (json.JSONDecodeError, TypeError):
        return None

    # Normalise: only keep the four known keys, default to None.
    allowed = {"rank", "title", "synopsis", "domain"}
    return {k: parsed.get(k) for k in allowed}


# ---------------------------------------------------------------------------
# 3. Atomic Persistence
# ---------------------------------------------------------------------------

_DEFAULT_OVERRIDES_PATH = Path(
    os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/overrides.json")
)


def save_override_to_file(
    gem_id: str,
    updates: dict,
    overrides_path: Optional[str | Path] = None,
) -> bool:
    """Atomically merge *updates* into the overrides JSON file.

    Uses BKM-022 compliant write-to-temp-then-replace to avoid corruption.

    Parameters
    ----------
    gem_id:
        Identifier to key the updates under (e.g. ``GEM-0142``).
    updates:
        Dictionary of field updates (e.g. ``{"rank": 5}``).
    overrides_path:
        Optional path to ``overrides.json``. Defaults to
        ``~/Dev_Lab/Portfolio_Dev/field_notes/data/overrides.json``.

    Returns
    -------
    True on successful write, False otherwise.
    """
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return True

    dest = Path(overrides_path) if overrides_path else _DEFAULT_OVERRIDES_PATH

    # Ensure parent directory exists.
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data (or start fresh).
    existing: dict[str, Any] = {}
    if dest.exists():
        try:
            with dest.open("r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = {}

    overrides: dict = existing.setdefault("overrides", {})
    merged: dict = overrides.setdefault(gem_id, {})
    merged.update(clean_updates)

    # Atomic write: serialise → write tmp → os.replace.
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2, ensure_ascii=False)
            fh.write("\n")  # trailing newline for POSIX
        os.replace(str(tmp_path), str(dest))
    except OSError:
        # Clean up partial tmp on failure.
        tmp_path.unlink(missing_ok=True)
        return False

    return True
