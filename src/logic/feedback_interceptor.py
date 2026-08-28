"""
[FEAT-456/FEAT-487] Language-First Co-Pilot Feedback Loop (BKM-035)

Intercepts user natural language disagreements and conversational corrections,
transforming them into permanent validation ledger FAIL records and in-character
refinement prompts.

BKM-015 Compliant: Uses structural regex patterns for critique detection
(linguistic structure, not domain-specific keyword matching).

[FEAT-487] DEPRECATION: The hardcoded regex pattern matching (`is_critique` /
`_CRITIQUE_PATTERNS`) is DROPPED as the primary feedback-detection path in favor
of model-driven semantic triage: the triage engine now classifies supervisory
feedback / bug reports / tone-verbosity corrections / Fourth-Wall commands to
`vibe: META`, `domain: feedback`, `addressed_to: SYSTEM`, and CognitiveHub's
fast control-plane intercept short-circuits on that classification.  These
regex helpers are preserved ONLY for backward compatibility and existing unit
tests; new feedback detection MUST go through the semantic triage path.

BKM-022 Compliant: Atomic file operations via .tmp + os.replace for JSONL writes.
"""

import datetime
import json
import os
import re
import tempfile
from typing import Optional


# [FEAT-487] DEPRECATED — superseded by model-driven semantic triage (vibe: META,
# domain: feedback). Kept for legacy tests only; do NOT extend this list.
# [BKM-015] Structural critique detection patterns.
# These detect the LINGUISTIC SHAPE of disagreement statements, NOT domain-specific
# keywords. This is compliant with BKM-015's prohibition of domain keyword hardcoding.
_CRITIQUE_PATTERNS = [
    # Direct correction patterns: "Wait, that's wrong", "No, X is Y"
    r"(?i)^(?:wait\s*[,!]?\s*(?:that'?s?\s+)?(?:wrong|incorrect|not\s+right|off))",
    r"(?i)^(?:no\s*[,!]?\s*(?:that'?s?\s+)?(?:wrong|incorrect|not\s+right))",
    # "Actually X is Y" corrections (excluding polite requests like "Actually, can you...")
    r"(?i)^actually\s*[,!]?\s+(?!(?:can|could|would|will|is|are|do|does|did|should)\s+(?:you|we|i)\b)\w",
    # Fourth-wall address patterns: "Pinky, note that", "Brain, you're wrong"
    r"(?i)^(?:pinky|brain|deep\s*thought)\s*[,!]?\s+(?:note\s+that|that'?s?\s+(?:wrong|incorrect|not)|you(?:'?re|\s+are)\s+(?:wrong|incorrect))",
    # Negation + correction: "X is not Y, it's Z" or "That is not ..., it should ..."
    r"(?i)\b(?:is|was|are|were)\s+not\s+\w.*(?:it'?s|it\s+is|that'?s|that\s+is|it\s+should|should\s+be)\s+",
    # Disagreement markers: "I disagree", "That's not right"
    r"(?i)^(?:i\s+)?(?:disagree|beg\s+to\s+differ)",
    r"(?i)^(?:that'?s?\s+)?not\s+(?:right|correct|accurate|true)",
    # Correction verbs with correction target: "correct me, but X is Y"
    r"(?i)^(?:to\s+)?(?:clarify|correct)\s*[:,]?\s+(?:that|it)\s+(?:is|was|should)",
]


def is_critique(query: str) -> bool:
    """
    [FEAT-456/BKM-035] Detect user disagreement or fourth-wall correction semantically.

    DEPRECATED ({FEAT-487}): Superseded by model-driven semantic triage. CognitiveHub
    no longer routes feedback through this regex pre-filter; it intercepts the
    vibe META / domain feedback classification from the triage engine instead.
    Retained only for backward compatibility and existing unit tests.

    Uses structural regex patterns to identify the LINGUISTIC SHAPE of critique
    statements (negation patterns, correction patterns, fourth-wall address).
    BKM-015 compliant: detects linguistic structure, NOT domain-specific keywords.

    Args:
        query: The raw user input string to classify.

    Returns:
        True if the query is detected as a user critique/correction, False otherwise.
    """
    if not query or not query.strip():
        return False

    normalized = query.strip()
    # Strip client-side transcript tags like [ME] or [USER]
    normalized = re.sub(r"^\[(?:ME|USER)\]\s*", "", normalized, flags=re.IGNORECASE).strip()

    # If it ends with a question mark and isn't a direct "Wait / No" objection, treat as question
    if normalized.endswith("?") and not re.search(r"(?i)^(?:wait|no\b)", normalized):
        return False

    for pattern in _CRITIQUE_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


# [BKM-035] Default validation ledger path
_DEFAULT_LEDGER_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl"
)


def record_feedback(
    query: str,
    flawed_output: str,
    user_correction: str,
    ledger_path: Optional[str] = None,
) -> dict:
    """
    [FEAT-456/BKM-035] Atomically append a FAIL record to validation_ledger.jsonl.

    BKM-022 Compliant: Uses .tmp + os.replace pattern for filesystem atomicity.
    Prevents consumers from encountering partially written JSONL entries.

    Schema (per BKM-035):
        {
            "timestamp": "ISO-8601",
            "query": "<original_user_query>",
            "verdict": "FAIL",
            "flawed_output": "<previous_assistant_response>",
            "ground_truth": "<user_correction_text>",
            "source": "CO_PILOT_FOURTH_WALL"
        }

    Args:
        query: The original user query that triggered the flawed output.
        flawed_output: The assistant response that contained the error.
        user_correction: The user's corrective statement.
        ledger_path: Optional override for the JSONL ledger path.
                     Defaults to ~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl.

    Returns:
        The FAIL record dict that was written to the ledger.
    """
    target_path = ledger_path or _DEFAULT_LEDGER_PATH

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "query": query,
        "verdict": "FAIL",
        "flawed_output": flawed_output,
        "ground_truth": user_correction,
        "source": "CO_PILOT_FOURTH_WALL",
    }

    # [BKM-022] Atomic file swap: read existing lines, write to .tmp, then os.replace
    ledger_dir = os.path.dirname(target_path)
    os.makedirs(ledger_dir, exist_ok=True)

    existing_lines = []
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as existing_f:
            existing_lines = existing_f.readlines()

    # Create temp file in same directory for atomic rename
    fd, tmp_path = tempfile.mkstemp(
        dir=ledger_dir, suffix=".tmp", prefix="validation_ledger_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            for line in existing_lines:
                tmp_file.write(line)
            tmp_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        # Atomic replace (BKM-022)
        os.replace(tmp_path, target_path)
    except Exception:
        # Cleanup temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return record


def generate_refinement_prompt(user_correction: str) -> str:
    """
    [FEAT-456/BKM-035] Generate Pinky's in-character acknowledgment with
    one targeted follow-up question.

    BKM-035 Behavioral Flow:
        1. Acknowledgment: Pinky acknowledges the correction in-character
           with high brevity.
        2. Refinement Inquiry: One targeted follow-up question to clarify
           boundary conditions, register masks, or reproduction steps.
        3. No Defensiveness: Never argue, hallucinate justifications, or
           provide conversational filler.

    Args:
        user_correction: The user's corrective statement.

    Returns:
        A string containing Pinky's acknowledgment and follow-up question.
    """
    # Extract the core factual correction (strip leading filler)
    correction_text = user_correction.strip()
    # Remove leading address patterns ("Pinky, " "Brain, " etc.)
    correction_text = re.sub(
        r"^(?:pinky|brain|deep\s*thought)\s*[:,!]?\s*",
        "",
        correction_text,
        flags=re.IGNORECASE,
    ).strip()

    # Build acknowledgment: brief, in-character, no defensiveness
    acknowledgment = f"Narf! Got it — {correction_text.rstrip('.')}."

    # Generate one targeted follow-up question to clarify boundary conditions
    follow_up = (
        " Should I update the runtime register mask "
        "to reflect this, or is this a one-off correction "
        "that only applies to the current query scope?"
    )

    return f"{acknowledgment}{follow_up}"
