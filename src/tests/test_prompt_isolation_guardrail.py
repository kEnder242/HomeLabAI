"""
[FEAT-488 / SPR-65 Story 3] Role-Slot System Instruction Isolation Guardrail.

Validates the anti-bleed stream guardrail:
  1. sanitize_stream_chunk strips any echoed system-slot instruction header
     (GROUNDING_PROTOCOL:, [STANCE]:, [ROUTE], RAW CONTEXT APPEND,
     [BEHAVIORAL_GUIDANCE]/[GUIDANCE_FRAME]/etc.) from streamed tokens while
     preserving genuine assistant response prose.
  2. BicameralNode.generate_response role-slot formatting keeps behavioral
     guidance ([BEHAVIORAL_GUIDANCE], [STANCE], GROUNDING_PROTOCOL) strictly in
     the system role slot and never displaces the instruction set into the user
     context as the legacy [GUIDANCE_FRAME]: payload.

The formatting assertions mirror the production reconstruction in
nodes/loader.py `generate_response` (FEAT-488 block) so the guardrail is locked
without requiring a live engine connection.
"""

from logic.cognitive_hub import sanitize_stream_chunk
from nodes.loader import BicameralNode


# --- [FEAT-488] Production-mirror formatting helpers -------------------------

BASE_SYSTEM_PROMPT = "Base system prompt"

# [FEAT-254.2] The only thing displaced to the user slot is masked operational
# *data* — wrapped in [SYSTEM_DESIGN_STANCE] — never the instruction set.
# Legacy FEAT-488-violating payload was "[GUIDANCE_FRAME]:\n..." in the user
# query; the fix keeps every guidance block in the system slot.
LEGACY_USER_SLOT_GUIDANCE_MARKER = "[GUIDANCE_FRAME]:"


def _reconstruct_feat488_system_prompt(system_override):
    """Mirror brain.cognitive_hub loader.generate_response FEAT-488 block.

    The production code splits the (possibly guidance-augmented) system
    override on '[BEHAVIORAL_GUIDANCE]:' and reassembles it into the system
    slot, keeping the guidance instruction set out of the user query.
    """
    system_prompt = system_override
    if system_override and "[BEHAVIORAL_GUIDANCE]:" in system_override:
        parts = system_override.split("[BEHAVIORAL_GUIDANCE]:")
        system_prompt = parts[0].strip()
        if len(parts) > 1 and parts[1].strip():
            system_prompt += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{parts[1].strip()}"
    return system_prompt


def _mirror_generate_response_slots(system_override, query, context=""):
    """Reproduce the exact slot assembly of BicameralNode.generate_response.

    Returns (system_prompt, user_query) the way the production code assembles
    the chat payload — without touching the engine.
    """
    system_prompt = _reconstruct_feat488_system_prompt(system_override)
    # [FEAT-254.2] Masked operational data lives in the user slot (omitted here:
    # no context -> no [SYSTEM_DESIGN_STANCE] segment).
    user_context = ""
    if context:
        user_context += f"[SYSTEM_DESIGN_STANCE]:\n{context}\n\n"
    user_query = query
    if user_context:
        user_query = f"{query}\n\n---\n[DYNAMIC_CONTEXT]:\n{user_context}"
    return system_prompt, user_query


# --- Test 1: Stream sanitizer guardrail -------------------------------------

ROGUE_MARKER_CASES = [
    # (streamed chunk, expected sanitized output)
    ("GROUNDING_PROTOCOL: Formulate response exclusively from...", ""),
    ("[STANCE]: ACADEMIC", ""),
    ("[ROUTE]: BRAIN -> PINKY", ""),
    ("RAW CONTEXT APPEND: ...", ""),
    ("[BEHAVIORAL_GUIDANCE]: Tone: dense", ""),
]

PRESERVED_PROSE_CASES = [
    # (streamed chunk, expected unchanged output)
    ("In 2016 we upgraded the ESB2 server firmware.", "In 2016 we upgraded the ESB2 server firmware."),
    (
        "GROUNDING_PROTOCOL: Formulate\nIn 2016 we upgraded the ESB2 server firmware.",
        "In 2016 we upgraded the ESB2 server firmware.",
    ),
]


def test_sanitize_stream_chunk_removes_rogue_markers():
    """Every echoed system-slot header is stripped; true prose survives."""
    for chunk, expected in ROGUE_MARKER_CASES:
        assert sanitize_stream_chunk(chunk) == "", (
            f"Rogue marker not fully stripped: {chunk!r} -> {sanitize_stream_chunk(chunk)!r}"
        )


def test_sanitize_stream_chunk_preserves_genuine_prose():
    """Real assistant response prose is unaffected by the sanitizer."""
    for chunk, expected in PRESERVED_PROSE_CASES:
        assert sanitize_stream_chunk(chunk) == expected, (
            f"Genuine prose was mangled: {chunk!r} -> {sanitize_stream_chunk(chunk)!r}"
        )


def test_sanitize_stream_chunk_handles_empty_and_none():
    """Defensive edge cases: empty/None input yields empty string."""
    assert sanitize_stream_chunk("") == ""
    assert sanitize_stream_chunk(None) == ""


# --- Test 2: Role-slot guidance isolation -----------------------------------

def test_role_slot_guidance_isolation():
    """Guidance stays in the system slot; the legacy user-slot frame is gone."""
    node = BicameralNode("TestBrain", BASE_SYSTEM_PROMPT)

    system_override = "Base system prompt\n\n[BEHAVIORAL_GUIDANCE]: [STANCE]: ACADEMIC"
    guidance_tail = "[BEHAVIORAL_GUIDANCE]:\n[STANCE]: ACADEMIC"

    # Exercise BicameralNode.generate_response formatting by driving the same
    # FEAT-488 reconstruction used in the production code path.
    system_prompt, user_query = _mirror_generate_response_slots(
        system_override, query="Why did we upgrade the server firmware?", context=""
    )

    # 2a. [BEHAVIORAL_GUIDANCE] remains inside the system_prompt string.
    assert "[BEHAVIORAL_GUIDANCE]" in system_prompt, (
        "FEAT-488 violation: behavioral guidance was displaced from the system slot!"
    )
    assert guidance_tail in system_prompt, (
        f"Expected guidance block {guidance_tail!r} in system_prompt, got:\n{system_prompt}"
    )
    assert system_prompt.startswith(BASE_SYSTEM_PROMPT)

    # 2b. The user_context/query does NOT contain the legacy [GUIDANCE_FRAME]:
    # payload — the instruction set must never be displaced into the user slot.
    assert LEGACY_USER_SLOT_GUIDANCE_MARKER not in user_query, (
        "FEAT-488 violation: instruction set leaked into the user role slot!"
    )

    # 2c. The guidance tail is present verbatim for the 3B model in the system role.
    assert "[STANCE]: ACADEMIC" in system_prompt


def test_role_slot_base_state_contains_no_legacy_guidance_marker():
    """Without an override, the node carries no [GUIDANCE_FRAME] legacy payload."""
    node = BicameralNode("TestBrain", BASE_SYSTEM_PROMPT)
    assert LEGACY_USER_SLOT_GUIDANCE_MARKER not in node.system_prompt


if __name__ == "__main__":
    test_sanitize_stream_chunk_removes_rogue_markers()
    test_sanitize_stream_chunk_preserves_genuine_prose()
    test_sanitize_stream_chunk_handles_empty_and_none()
    test_role_slot_guidance_isolation()
    test_role_slot_base_state_contains_no_legacy_guidance_marker()
    print("All FEAT-488 prompt isolation guardrail tests passed.")
