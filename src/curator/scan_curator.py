"""Universal Epistemic 5-Question Battery for gem quality evaluation.

This module implements a deterministic, binary assertion-based evaluation
system replacing fuzzy 1-5 integer scoring with 5 atomic boolean checks.
"""

import re
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Physical register / port / error‑code lexicon used by
# ``has_exact_identifiers``.  Each entry is a compiled regex.
# ──────────────────────────────────────────────────────────────────────────────
_IDENTIFIER_PATTERNS: list[re.Pattern[str]] = [
    # MSR addresses – e.g. MSR 0x610, MSR 0x1A0
    re.compile(r"\bMSR\s+0x[0-9A-Fa-f]+\b", re.IGNORECASE),
    # Numeric port – e.g. port 8088, port 443
    re.compile(r"\bport\s+\d{2,5}\b", re.IGNORECASE),
    # PCIe AER registers – e.g. PCIe AER 0x10, AER 0x10
    re.compile(r"\b(?:PCIe\s+)?AER\s+0x[0-9A-Fa-f]+\b", re.IGNORECASE),
    # General hex register – e.g. register 0xDEAD, reg 0x1
    re.compile(r"\b(?:register|reg)\s+0x[0-9A-Fa-f]+\b", re.IGNORECASE),
    # Generic error code – e.g. error code 0x80070005, errno 2
    re.compile(r"\b(?:error\s+code|errno)\s+\S+\b", re.IGNORECASE),
]


def has_exact_identifiers(text: str) -> bool:
    """Return ``True`` if *text* mentions a physical register, port, or
    error code that grounds the discussion in concrete hardware / firmware
    reality.

    Checks for patterns like ``MSR 0x610``, ``port 8088``,
    ``PCIe AER 0x10``, ``register 0xDEAD``, ``errno 2``, etc.
    """
    return any(p.search(text) for p in _IDENTIFIER_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# CLI / script reproduction‑recipe lexicon.
# ──────────────────────────────────────────────────────────────────────────────
_RECIPE_PATTERNS: list[re.Pattern[str]] = [
    # Markdown fenced code block (```bash … ```)
    re.compile(r"```\w*\n.+\n```", re.DOTALL),
    # One-liner CLI snippet – e.g. ``sudo dmesg | grep -i mce``
    re.compile(r"`[^`\n]{8,}`"),
    # Explicit shell keywords that signal copy‑pastable commands
    re.compile(r"\b(?:sudo\s+\w+|apt(?:-get)?\s+\w+|yum\s+\w+|pip\s+\w+|"
               r"curl\s+\w+|wget\s+\w+|modprobe\s+\w+|dmesg\s+\w+|"
               r"journalctl\s+\w+|systemctl\s+\w+|echo\s+[\"']?\S+)\b"),
]


def has_reproduction_recipe(text: str) -> bool:
    """Return ``True`` if *text* contains a copy‑pasteable CLI command or
    script block that a reader can run to reproduce or diagnose the issue.
    """
    return any(p.search(text) for p in _RECIPE_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# Cause‑and‑effect isolation patterns.
# ──────────────────────────────────────────────────────────────────────────────
_CAE_PATTERNS: list[re.Pattern[str]] = [
    # Causal connectors
    re.compile(r"\b(?:because|caused by|due to|results? in|leads? to|"
               r"triggers?|activates?|induces?)\b", re.IGNORECASE),
    # Mechanism verbs followed by direction
    re.compile(r"\b(?:failure\s+mechanism|root\s+cause|underlying\s+cause|"
               r"direct\s+cause|proximate\s+cause)\b", re.IGNORECASE),
]


def isolates_cause_and_effect(text: str) -> bool:
    """Return ``True`` if *text* explicitly articulates a causal chain —
    the failure mechanism that links trigger to symptom.
    """
    return any(p.search(text) for p in _CAE_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# Actionable BKM (Best Known Method) patterns.
# ──────────────────────────────────────────────────────────────────────────────
_ACTIONABLE_PATTERNS: list[re.Pattern[str]] = [
    # Step‑by‑step instructions
    re.compile(r"(?:^|\n)\s*(?:\d+[\.\)]\s+|Step\s+\d+)", re.MULTILINE),
    # Imperative verbs at start of sentence – "Run …", "Edit …", "Replace …"
    re.compile(r"(?:^|\n)\s*(?:Run|Edit|Replace|Remove|Add|Set|Disable|"
               r"Enable|Install|Upgrade|Downgrade|Reboot|Reset)\b",
               re.MULTILINE | re.IGNORECASE),
    # Explicit resolution language
    re.compile(r"\b(?:resolution\s+procedure|fix\s+procedure|"
               r"remediation\s+steps?|workaround\s+steps?)\b", re.IGNORECASE),
]


def is_actionable_bkm(text: str) -> bool:
    """Return ``True`` if *text* provides a directly executable resolution
    procedure — numbered steps, imperative commands, or explicit remediation
    language.
    """
    return any(p.search(text) for p in _ACTIONABLE_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# Conversational‑fluff detector.
# ──────────────────────────────────────────────────────────────────────────────
_FLUFF_PATTERNS: list[re.Pattern[str]] = [
    # Greetings / filler openers
    re.compile(r"\b(?:Hello|Hi|Hey|Greetings|Dear\s+\w+|"
               r"Good\s+(?:morning|afternoon|evening))\b", re.IGNORECASE),
    # Hedging / apology phrases
    re.compile(r"\b(?:I\s+think|I\s+believe|I\s+feel|it\s+seems\s+like|"
               r"maybe|perhaps|I'm\s+not\s+sure|I\s+could\s+be\s+wrong|"
               r"just\s+my\s+opinion)\b", re.IGNORECASE),
    # Excessive politeness / filler closers
    re.compile(r"\b(?:Hope\s+this\s+helps|Let\s+me\s+know|"
               r"Feel\s+free\s+to\s+ask|Happy\s+to\s+help|"
               r"Please\s+don't\s+hesitate)\b", re.IGNORECASE),
]


def has_zero_conversational_fluff(text: str) -> bool:
    """Return ``True`` if *text* is free of conversational filler —
    greetings, hedging, apologies, or excessive politeness that add no
    technical substance.
    """
    return not any(p.search(text) for p in _FLUFF_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────
# Battery execution
# ──────────────────────────────────────────────────────────────────────────────
_CHECKS: list[tuple[str, callable]] = [
    ("has_exact_identifiers", has_exact_identifiers),
    ("has_reproduction_recipe", has_reproduction_recipe),
    ("isolates_cause_and_effect", isolates_cause_and_effect),
    ("is_actionable_bkm", is_actionable_bkm),
    ("has_zero_conversational_fluff", has_zero_conversational_fluff),
]


def _compute_rank(checks: dict[str, bool]) -> int:
    """Deterministic rank: 1 + number of passing checks, capped at 5."""
    return min(5, 1 + sum(checks.values()))


def evaluate_gem_quality(text: str) -> dict[str, Any]:
    """Run the Universal Epistemic 5‑Question Battery on *text* and return
    a structured result.

    Returns
    -------
    dict
        ``{"rank": int, "checks": {check_name: bool, ...}}``

        * **rank** – integer in ``[1, 5]`` where ``1`` means zero checks
          pass and ``5`` means all five pass.
        * **checks** – mapping of each check name to its boolean result.
    """
    checks: dict[str, bool] = {}
    for name, fn in _CHECKS:
        checks[name] = bool(fn(text))

    rank = _compute_rank(checks)
    return {"rank": rank, "checks": checks}
