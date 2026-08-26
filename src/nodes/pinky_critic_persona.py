"""
[FEAT-470] Pinky Critic Persona Satellite

Pure, stateless decoupled module implementing the Pinky Critic persona's
prompt construction, response parsing, chat delivery formatting, and
crosstalk telemetry emission.

BKM-015 Compliant: zero third-party dependencies beyond the Python standard
library.  SpeakerRegistry imported from triage_engine when available, with
a dynamic regex fallback otherwise.

Class 1 Design: all functions are side-effect free and testable in isolation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SpeakerRegistry Import (graceful fallback)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from logic.triage_engine import SpeakerRegistry
except ImportError:
    try:
        from src.logic.triage_engine import SpeakerRegistry
    except ImportError:
        SpeakerRegistry = None  # type: ignore[assignment,misc]


def _build_fallback_stripper() -> re.Pattern[str]:
    """Build a regex that strips bracketed and colon-delimited speaker prefixes."""
    return re.compile(
        r"^(?:\[(?:[^\]]+)\]|\b\w+\b:)\s*",
        flags=re.IGNORECASE,
    )


_FALLBACK_STRIPPER = _build_fallback_stripper()


def _strip_speaker_prefix(text: str) -> str:
    """Remove leading speaker prefix from *text*.

    Uses ``SpeakerRegistry.sanitize`` when available; otherwise falls back
    to a general-purpose regex that strips ``[Name]``, ``[ROLE: Name]``, and
    ``Name:`` style prefixes.
    """
    if SpeakerRegistry is not None:
        return SpeakerRegistry().sanitize(text)

    prev: str | None = None
    curr = text.strip()
    while prev != curr:
        prev = curr
        curr = _FALLBACK_STRIPPER.sub("", curr).strip()
    return curr


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Banned robotic phrases
# ═══════════════════════════════════════════════════════════════════════════════

_BANNED_PHRASES: list[str] = [
    "A well-crafted response",
    "Here is a well-crafted response",
    "well-crafted response",
    "well crafted response",
    "well-crafted",
    "well crafted",
    "I hope this helps",
    "Let me know if you have any questions",
    "In conclusion",
    "As an AI",
    "Certainly!",
    "Of course!",
    "Great question!",
    "Absolutely!",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. build_critic_prompt
# ═══════════════════════════════════════════════════════════════════════════════

def build_critic_prompt(
    user_query: str,
    technical_summary: str,
    *,
    persona_name: str = "Pinky",
    critique_dimensions: list[str] | None = None,
) -> str:
    """Build a structured JSON prompt for the Pinky Critic persona.

    Parameters
    ----------
    user_query:
        The original user query being critiqued.
    technical_summary:
        The agreed technical summary to weave into the delivery.
    persona_name:
        Override the persona label (default ``"Pinky"``).
    critique_dimensions:
        Optional list of critique axes (e.g. ``["accuracy", "tone"]``).

    Returns
    -------
    A JSON-formatted string that instructs the LLM to return a structured
    critique payload with ``cartoon_retort``, ``critique_suggestions``,
    and ``banned_phrases``.

    Raises
    ------
    ValueError
        When *user_query* or *technical_summary* is empty or whitespace-only.
    """
    if not user_query or not user_query.strip():
        raise ValueError("user_query must be non-empty")
    if not technical_summary or not technical_summary.strip():
        raise ValueError("technical_summary must be non-empty")

    dimensions = critique_dimensions or ["accuracy", "tone", "completeness"]

    payload: dict[str, Any] = {
        "persona": persona_name,
        "user_query": user_query.strip(),
        "technical_summary": technical_summary.strip(),
        "critique_dimensions": dimensions,
        "banned_phrases": _BANNED_PHRASES,
        "output_schema": {
            "cartoon_retort": "string — a witty, in-character one-liner",
            "critique_suggestions": "list[string] — actionable improvement notes",
        },
    }
    return json.dumps(payload, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. parse_critic_payload
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CriticResult:
    """Structured result from :func:`parse_critic_payload`."""

    cartoon_retort: str
    critique_suggestions: list[str]
    score: int = 5
    reasoning: str = ""
    slop_found: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def retort(self) -> str:
        """Alias for :attr:`cartoon_retort` for backward compatibility."""
        return self.cartoon_retort


def parse_critic_payload(raw_response: str) -> CriticResult:
    """Parse the LLM's structured JSON response into a :class:`CriticResult`.

    Handles three resilience cases:
      1. Clean JSON payload.
      2. JSON embedded in surrounding prose (``{…}`` extraction).
      3. Unparseable response → safe fallback with the raw text as retort.

    Parameters
    ----------
    raw_response:
        The raw string returned by the LLM.

    Returns
    -------
    A :class:`CriticResult` with at minimum a ``cartoon_retort`` and a
    (possibly empty) ``critique_suggestions`` list.
    """
    if not raw_response or not raw_response.strip():
        return CriticResult(
            cartoon_retort="Narf! The critic drew a blank.",
            critique_suggestions=[],
        )

    text = raw_response.strip()

    # --- Case 1: clean JSON ---
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return _coerce_result(data)
    except (json.JSONDecodeError, TypeError):
        pass

    # --- Case 2: JSON embedded in prose ---
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return _coerce_result(data)
        except (json.JSONDecodeError, TypeError):
            pass

    # --- Case 3: unparseable → fallback ---
    return CriticResult(
        cartoon_retort=text[:200],
        critique_suggestions=["LLM returned unstructured payload."],
    )


def _coerce_result(data: dict[str, Any]) -> CriticResult:
    """Coerce a dict into a :class:`CriticResult` with safe defaults."""
    retort = str(data.get("cartoon_retort", "")).strip()
    if not retort:
        retort = "Narf! The retort went missing."

    suggestions_raw = data.get("critique_suggestions", [])
    if isinstance(suggestions_raw, list):
        suggestions = [str(s) for s in suggestions_raw if s]
    else:
        suggestions = [str(suggestions_raw)] if suggestions_raw else []

    # Extract optional telemetry fields with safe defaults
    score = int(data.get("score", 5)) if data.get("score") is not None else 5
    reasoning = str(data.get("reasoning", "")).strip() if data.get("reasoning") else ""
    slop_found = bool(data.get("slop_found", False))

    return CriticResult(
        cartoon_retort=retort,
        critique_suggestions=suggestions,
        score=score,
        reasoning=reasoning,
        slop_found=slop_found,
        raw=data,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. format_chat_delivery
# ═══════════════════════════════════════════════════════════════════════════════

def format_chat_delivery(
    cartoon_retort: str,
    technical_summary: str,
    *,
    banned_phrases: list[str] | None = None,
) -> str:
    """Blend a witty cartoon quip with the technical summary for chat delivery.

    The output is the *cartoon_retort* followed by a blank line and the
    sanitised *technical_summary*.  The method:

    - Strips any leading speaker prefix from both inputs.
    - Removes banned robotic boilerplate phrases from the retort.
    - Returns an empty string if both inputs are empty.

    Parameters
    ----------
    cartoon_retort:
        The witty one-liner from the critic.
    technical_summary:
        The agreed technical summary to append.
    banned_phrases:
        Override the default banned-phrase list.

    Returns
    -------
    A blended delivery string safe for chat output.
    """
    bans = banned_phrases if banned_phrases is not None else _BANNED_PHRASES

    retort = _strip_speaker_prefix(cartoon_retort)
    summary = _strip_speaker_prefix(technical_summary)

    # Strip banned phrases from both retort and summary
    for phrase in bans:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        retort = pattern.sub("", retort).strip()
        summary = pattern.sub("", summary).strip()

    # Clean residual punctuation at boundaries
    retort = re.sub(r"^[\s.,;:!?\-]+", "", retort).strip()
    summary = re.sub(r"^[\s.,;:!?\-]+", "", summary).strip()

    # Collapse any double-blanks left by removal
    retort = re.sub(r"\s{2,}", " ", retort).strip()
    summary = re.sub(r"\s{2,}", " ", summary).strip()

    if not retort and not summary:
        return ""
    if not retort:
        return summary
    if not summary:
        return retort

    return f"{retort}\n\n{summary}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. format_crosstalk_telemetry
# ═══════════════════════════════════════════════════════════════════════════════

def format_crosstalk_telemetry(
    *,
    source_persona: str = "Pinky",
    target_persona: str = "Brain",
    payload: dict[str, Any],
    prompt: str = "",
    raw_response: str = "",
    source: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """Wrap a critic exchange into a crosstalk telemetry envelope.

    The envelope is consumed by downstream telemetry collectors and
    broadcast managers for routing, audit, and observability.

    Parameters
    ----------
    source_persona:
        The persona emitting the critique (e.g. ``"Pinky"``).
    target_persona:
        The persona being critiqued (e.g. ``"Brain"``).
    payload:
        The parsed :class:`CriticResult`-compatible dict.
    prompt:
        The prompt that was sent to the LLM (optional, for audit).
    raw_response:
        The raw LLM response (optional, for audit).
    source:
        Optional alias for source_persona.
    target:
        Optional alias for target_persona.

    Returns
    -------
    A telemetry envelope dict with standard fields.
    """
    src = source if source is not None else source_persona
    tgt = target if target is not None else target_persona
    return {
        "crosstalk": True,
        "source": src,
        "target": tgt,
        "payload": payload,
        "prompt": prompt,
        "raw_response": raw_response,
    }
