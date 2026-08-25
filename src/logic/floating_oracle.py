"""
[FEAT-458] Conversational WYWO & Floating Validation Oracle

Harvests ambient telemetry from the lab's filesystem artifacts and assembles
floating context candidates for organic injection into conversation turns.

Subsystems consumed:
  - validation_ledger.jsonl  (BKM-035 FAIL records from feedback_interceptor)
  - scan_state.json / chunk_state.json (mass-scan milestone bookkeeping)
  - nightly_dialogue.json    (WYWO morning briefings from dream_node)

BKM-015 Compliant: shallow-turn detection uses structural regex patterns
(linguistic shape, not domain-specific keyword matching).

BKM-022 Compliant: all file reads are guarded with atomic fallback paths.

Class 1 Design: zero third-party dependencies beyond the Python standard library.
"""

import json
import os
import re
from typing import Optional


# ─── Default Paths ────────────────────────────────────────────────────────────

_DEFAULT_LEDGER_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl"
)
_DEFAULT_SCAN_STATE_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/scan_state.json"
)
_DEFAULT_CHUNK_STATE_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/chunk_state.json"
)
_DEFAULT_DIALOGUE_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json"
)


# ─── Shallow Turn Detection (BKM-015 Compliant) ─────────────────────────────

# Structural patterns that detect GREETINGS and OPEN-ENDED INQUIRIES by their
# linguistic shape. BKM-015 compliant: no domain-specific keywords hardcoded.
_SHALLOW_TURN_PATTERNS = [
    # ── Greetings ──────────────────────────────────────────────────────────
    # Bare salutations: "hey", "hi", "hello", "yo", "narf"
    r"(?i)^(?:hey|hi|hello|yo|narf|good\s+(?:morning|afternoon|evening))\b[\s!,.]*$",
    # Greeting + address: "hey pinky", "hi brain"
    r"(?i)^(?:hey|hi|hello|yo)\s+(?:pinky|brain|deep\s*thought)\b[\s!,.]*$",
    # Greeting + soft opener: "hey, how are you", "hi, what's up", "hey pinky, how are things"
    r"(?i)^(?:hey|hi|hello|yo)(?:\s+(?:pinky|brain|deep\s*thought|mice))?\b[\s!,.]+(?:how\s+(?:are|r)\s+(?:you|things|it\s+going)|what'?s\s+up|sup|how'?s\s+(?:it\s+going|things))\b",
    # ── Open-Ended Inquiries ──────────────────────────────────────────────
    # Status checks: "how are things", "what's the status"
    # Note: how's → how'?s? handles the contraction (no \s+ between how and apostrophe)
    r"(?i)^(?:how(?:'?s|\s+(?:are|(?:'|e)r))\s+(?:things|we|the\s+lab|it\s+going|you))\b",
    r"(?i)^(?:what'?s\s+(?:the\s+)?(?:status|up|new|happening|going\s+on))\b",
    # Soft checks: "anything new", "what have I missed"
    r"(?i)^(?:anything\s+new|what\s+have\s+(?:i|we)\s+missed|what'?s\s+going\s+on)\b[\s!,.]*$",
    # "How are you" variants
    r"(?i)^how\s+(?:are|r)\s+you\b[\s!,.]*$",
    # "What's up" variants
    r"(?i)^what'?s\s+up\b[\s!,.]*$",
]


def is_shallow_turn(query: str) -> bool:
    """
    [FEAT-458/BKM-015] Detect semantic greetings and open-ended inquiries.

    Uses structural regex patterns to identify the LINGUISTIC SHAPE of
    shallow-turn utterances (greetings, status checks, soft openers).
    BKM-015 compliant: detects linguistic structure, NOT domain-specific keywords.

    A shallow turn is one where the user is *checking in* rather than issuing
    a technical query. The FloatingOracle uses this to decide whether to
    inject ambient context candidates.

    Args:
        query: The raw user input string to classify.

    Returns:
        True if the query is a shallow turn (greeting / open-ended inquiry),
        False otherwise.
    """
    if not query or not query.strip():
        return False

    normalized = query.strip()

    # Questions ending with "?" are generally NOT shallow turns unless they
    # match a status-check pattern (handled below).
    for pattern in _SHALLOW_TURN_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


# ─── Harvesting Methods ──────────────────────────────────────────────────────


def harvest_validation_scar(ledger_path: Optional[str] = None) -> Optional[str]:
    """
    [FEAT-458] Harvest the most recent FAIL entry from validation_ledger.jsonl.

    Reads the JSONL ledger written by feedback_interceptor.record_feedback
    (BKM-035) and returns a one-line scar digest suitable for floating context
    injection.

    Args:
        ledger_path: Optional override. Defaults to the BKM-035 standard path.

    Returns:
        A formatted scar digest string, or None if no FAIL entries exist or
        the file is unreadable.
    """
    target = ledger_path or _DEFAULT_LEDGER_PATH

    if not os.path.isfile(target):
        return None

    try:
        last_fail = None
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("verdict") == "FAIL":
                    last_fail = record

        if last_fail is None:
            return None

        # Build a concise scar digest
        query = last_fail.get("query", "unknown query")
        ground_truth = last_fail.get("ground_truth", "unknown correction")
        timestamp = last_fail.get("timestamp", "unknown time")

        return (
            f"[VALIDATION_SCAR]: Recent FAIL at {timestamp} — "
            f"query: \"{query}\" | ground truth: \"{ground_truth}\""
        )

    except Exception:
        return None


def harvest_mass_scan_progress(state_path: Optional[str] = None) -> Optional[str]:
    """
    [FEAT-458] Harvest a recent milestone from scan_state.json or chunk_state.json.

    Attempts scan_state.json first, falls back to chunk_state.json. Returns a
    concise progress digest describing the latest scan milestone or chunk state.

    Args:
        state_path: Optional override for the primary state file path.

    Returns:
        A formatted progress digest string, or None if no milestone data exists.
    """
    target = state_path or _DEFAULT_SCAN_STATE_PATH

    # If user explicitly provided a path, only try that one (no fallback).
    if state_path is not None:
        paths_to_try = [target]
    else:
        # Default: try scan_state.json first, then chunk_state.json
        paths_to_try = [target, _DEFAULT_CHUNK_STATE_PATH]

    for path in paths_to_try:

        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        # Extract milestone information from available keys
        milestone = (
            data.get("milestone")
            or data.get("last_milestone")
            or data.get("progress")
            or data.get("status")
            or data.get("phase")
        )
        if milestone:
            total = data.get("total_chunks") or data.get("total") or data.get("count")
            completed = data.get("completed") or data.get("processed") or data.get("done")

            parts = [f"[SCAN_PROGRESS]: {milestone}"]
            if total is not None and completed is not None:
                parts.append(f"{completed}/{total}")
            elif total is not None:
                parts.append(f"(total: {total})")

            return " — ".join(parts)

        # If no milestone key, but file has meaningful content, report it
        if data:
            # Pick the first non-timestamp key as a summary
            keys = [k for k in data if k not in ("timestamp", "updated_at", "last_updated")]
            if keys:
                first_val = data[keys[0]]
                if isinstance(first_val, str):
                    return f"[SCAN_PROGRESS]: {keys[0]} = {first_val}"

    return None


def harvest_subconscious_dream(dialogue_path: Optional[str] = None) -> Optional[str]:
    """
    [FEAT-458] Harvest the latest synthesis from nightly_dialogue.json.

    Reads the WYWO Morning Briefing persisted by dream_node and returns a
    concise digest of the topic and key content for floating context injection.

    Schema expected (from dream_node._build_wywo_briefing):
        {
            "timestamp": "YYYY-MM-DD HH:MM:SS",
            "topic": "WYWO Morning Briefing — YYYY-MM-DD",
            "content": "PINKY: ... THE BRAIN: ...",
            "type": "WYWO_MORNING_BRIEFING",
            "creative_ideas": [...]
        }

    Args:
        dialogue_path: Optional override. Defaults to the dream_node standard path.

    Returns:
        A formatted dream digest string, or None if no dialogue exists.
    """
    target = dialogue_path or _DEFAULT_DIALOGUE_PATH

    if not os.path.isfile(target):
        return None

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, dict):
        return None

    topic = data.get("topic", "untitled")
    content = data.get("content", "")
    timestamp = data.get("timestamp", "unknown time")

    if not content:
        return None

    # Truncate content to a reasonable floating-context snippet
    snippet = content[:300].strip()
    if len(content) > 300:
        snippet += "..."

    return (
        f"[SUBCONSCIOUS_DREAM]: {topic} ({timestamp}) — {snippet}"
    )


# ─── Floating Candidate Pool ────────────────────────────────────────────────


def build_floating_candidate_pool(
    validation_scar: Optional[str] = None,
    scan_progress: Optional[str] = None,
    dream_synthesis: Optional[str] = None,
    auto_harvest: bool = False,
) -> str:
    """
    [FEAT-458] Assemble up to 3 ambient context candidates into a floating
    prompt block for organic conversation injection.

    Each candidate is harvested from a different lab subsystem. The pool is
    designed for use with temperature T=0.7 to encourage organic steering
    toward unresolved lab context without forcing topic transitions.

    Args:
        validation_scar: Optional scar digest from harvest_validation_scar.
        scan_progress:   Optional progress digest from harvest_mass_scan_progress.
        dream_synthesis: Optional dream digest from harvest_subconscious_dream.
        auto_harvest:    If True, automatically harvest missing candidates from disk.

    Returns:
        A formatted prompt block string. Always returns a valid block even
        if all candidates are None (returns an empty placeholder block).
    """
    candidates = []

    scar = validation_scar if validation_scar is not None else (harvest_validation_scar() if auto_harvest else None)
    prog = scan_progress if scan_progress is not None else (harvest_mass_scan_progress() if auto_harvest else None)
    dream = dream_synthesis if dream_synthesis is not None else (harvest_subconscious_dream() if auto_harvest else None)

    if scar:
        candidates.append(scar)
    if prog:
        candidates.append(prog)
    if dream:
        candidates.append(dream)

    header = "[FLOATING_CANDIDATES]"
    instruction = (
        "Steer organically via temperature T=0.7. "
        "If any candidate resonates with the user's current query, "
        "surface it naturally. Otherwise, let the conversation flow."
    )

    if not candidates:
        return (
            f"{header}\n"
            f"No ambient candidates available.\n"
            f"{instruction}"
        )

    pool_lines = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(candidates))

    return (
        f"{header}\n"
        f"{pool_lines}\n"
        f"{instruction}"
    )
