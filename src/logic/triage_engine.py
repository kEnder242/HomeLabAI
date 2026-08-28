"""
[FEAT-467/468/471] Decoupled Triage Engine Satellite

Pure, stateless decision and sanitization module extracted from CognitiveHub.
Implements speaker demarcation, HyDE template scrubbing, meta-lexicon
classification, and vibe/domain routing for the unified pre-reflection
triage pipeline.

BKM-015 Compliant: meta-lexicon detection uses structural keyword matching
against live lab module names (not hardcoded domain jargon).

Class 1 Design: zero third-party dependencies beyond the Python standard library.
"""

from __future__ import annotations

import json
import re
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SpeakerRegistry – Dynamic Runtime Persona Sanitizer
# ═══════════════════════════════════════════════════════════════════════════════


class SpeakerRegistry:
    """Dynamic speaker sanitizer that scales automatically with registered personas.

    Builds a single compiled regex from all registered names that matches
    bracketed tags like ``[Pinky]``, ``[USER: Jason]``, and colon-delimited
    prefixes like ``Brain:``.  The :meth:`sanitize` method strips these
    prefixes iteratively until the text stabilises, handling nested / dirty
    leading markup.

    Parameters
    ----------
    names:
        Optional list of speaker names.  Defaults to the standard lab
        roster when *None*.
    """

    _DEFAULT_NAMES: list[str] = [
        "Pinky",
        "Brain",
        "Deep Thought",
        "Archive",
        "Lab",
        "User",
        "Jason",
        "Assistant",
        "System",
        "Me",
    ]

    def __init__(self, names: list[str] | None = None) -> None:
        self.names: list[str] = names if names is not None else list(self._DEFAULT_NAMES)
        escaped = "|".join(re.escape(n) for n in self.names)
        self._pattern: re.Pattern[str] = re.compile(
            rf"^(?:\[(?:{escaped})(?::[^\]]*)?\]|\b(?:{escaped})\b:)\s*",
            flags=re.IGNORECASE,
        )

    def sanitize(self, text: str) -> str:
        """Strip leading speaker prefixes until the text stabilises.

        Handles nested / dirty prefixes such as ``[Pinky] Brain: Hello``
        by iterating until no further changes occur.
        """
        prev: str | None = None
        curr = text.strip()
        while prev != curr:
            prev = curr
            curr = self._pattern.sub("", curr).strip()
        return curr


# ═══════════════════════════════════════════════════════════════════════════════
# 2. extract_latest_user_query
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_REGISTRY = SpeakerRegistry()


def extract_latest_user_query(turn_or_history: str) -> str:
    """Extract exclusively the latest user command from *turn_or_history*.

    Strips ``[ME]``, ``[USER]``, ``[User: Jason]``, and any other registered
    speaker prefix via :class:`SpeakerRegistry`.  Returns the cleaned text.

    Parameters
    ----------
    turn_or_history:
        A single turn string or the final line of a multi-turn history block.
    """
    if not turn_or_history or not turn_or_history.strip():
        return ""

    # If multi-line, take the last non-empty line.
    lines = [line for line in turn_or_history.strip().splitlines() if line.strip()]
    raw = lines[-1] if lines else turn_or_history.strip()

    return _DEFAULT_REGISTRY.sanitize(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. format_speaker_history
# ═══════════════════════════════════════════════════════════════════════════════

_ROLE_TAG_MAP: dict[str, str] = {
    "user": "USER",
    "assistant": "ASSISTANT",
    "system": "SYSTEM",
}


def format_speaker_history(history_turns: list[dict[str, str]]) -> str:
    """Format internal prompt memory with structured speaker tags.

    Each turn dict must contain ``role`` (``"user"`` | ``"assistant"`` |
    ``"system"``) and ``content``.  An optional ``name`` field tags the
    speaker (e.g. ``"Pinky"``).

    Returns a multi-line string with tags like::

        [USER: Jason] What is the PCIe error count?
        [ASSISTANT: Brain] The AER log shows 3 uncorrectable errors.

    Parameters
    ----------
    history_turns:
        List of ``{"role": ..., "content": ..., "name": ...}`` dicts.
    """
    if not history_turns:
        return ""

    parts: list[str] = []
    for turn in history_turns:
        role_raw = str(turn.get("role", "user")).lower()
        role_tag = _ROLE_TAG_MAP.get(role_raw, role_raw.upper())
        name = turn.get("name", "")
        content = str(turn.get("content", "")).strip()

        if name:
            tag = f"[{role_tag}: {name}]"
        else:
            tag = f"[{role_tag}]"

        parts.append(f"{tag} {content}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. scrub_hyde_vector
# ═══════════════════════════════════════════════════════════════════════════════

_TEMPLATE_ANGLE_BRACKET_RE = re.compile(r"<[^>]*>")


def scrub_hyde_vector(hyde_text: str) -> str:
    """Strip template angle brackets from a HyDE vector string.

    Removes literal ``<…>`` placeholders (e.g. ``<silicon_term_or_pcie_ras>``)
    that may leak from few-shot templates.  Returns an empty string when the
    input is empty, None-like, or becomes empty after scrubbing (ambiguous /
    useless vector → enforce Zero Context rule).

    Parameters
    ----------
    hyde_text:
        The raw HyDE vector text produced by the triage LLM.
    """
    if not hyde_text or not isinstance(hyde_text, str):
        return ""

    stripped = _TEMPLATE_ANGLE_BRACKET_RE.sub("", hyde_text)
    # Collapse whitespace left by removed placeholders
    stripped = re.sub(r"\s+", " ", stripped).strip()

    if not stripped:
        return ""

    return stripped


# ═══════════════════════════════════════════════════════════════════════════════
# 5. is_meta_lexicon
# ═══════════════════════════════════════════════════════════════════════════════

_META_KEYWORDS: frozenset[str] = frozenset(
    {
        "audio_pipeline",
        "maintenance_sweeper",
        "override_parser",
        "foyer",
        "vllm",
        "attendant",
        "residents",
        "features",
        "bkm",
    }
)


def is_meta_lexicon(query: str) -> bool:
    """Identify live system component keywords in *query*.

    Returns ``True`` when the lowercased query contains any of the known
    lab-module keywords that indicate the user is talking about the lab's
    own infrastructure rather than an external technical topic.

    Parameters
    ----------
    query:
        The user's query string.
    """
    if not query or not query.strip():
        return False

    tokens = set(re.findall(r"[a-z_]+", query.lower()))
    return bool(_META_KEYWORDS & tokens)


try:
    from logic.triage_policy_loader import TriagePolicyLoader
    from logic.route_incubator import RouteIncubator
except ImportError:
    try:
        from triage_policy_loader import TriagePolicyLoader
        from route_incubator import RouteIncubator
    except ImportError:
        TriagePolicyLoader = None  # type: ignore
        RouteIncubator = None  # type: ignore

_DEFAULT_POLICY_LOADER = TriagePolicyLoader() if TriagePolicyLoader else None
_DEFAULT_INCUBATOR = RouteIncubator() if RouteIncubator else None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. classify_vibe_and_domain
# ═══════════════════════════════════════════════════════════════════════════════

_META_DOMAIN_OVERRIDES: dict[str, str] = {
    "vibe": "META",
    "domain": "lab_internal",
}


# [FEAT-487 / BKM-035] Control-plane feedback detection. A META turn whose resolved
# domain is in this set (or unset) is supervisory feedback destined for the fast
# control-plane intercept — NOT a lab-internal meta-status query, which carries
# domain "lab_internal" and must never be swallowed as feedback.
_FEEDBACK_DOMAINS: frozenset[str] = frozenset({"feedback", "standard", ""})


def is_control_plane_feedback(t_parsed: dict[str, Any]) -> bool:
    """Return ``True`` when a parsed triage dict is supervisory feedback (FEAT-487/BKM-035).

    Semantic, BKM-015-compliant structural field inspection — it does NOT
    pattern-match the user's free text.  A turn is control-plane feedback when
    the triage model resolved it to the ``META`` vibe with a feedback/standard
    domain, OR explicitly set ``domain == "feedback"``.  Lab-internal meta-status
    turns (``domain == "lab_internal"``) and retrieval turns (``exp_*`` /
    ``lab_history``) are never treated as feedback.
    """
    if not isinstance(t_parsed, dict):
        return False
    vibe = str(t_parsed.get("vibe", "")).upper()
    domain = str(t_parsed.get("domain", "")).lower()
    if domain == "feedback":
        return True
    if vibe == "META" and domain in _FEEDBACK_DOMAINS:
        return True
    return False


def classify_vibe_and_domain(
    query: str,
    parsed_json: dict[str, Any],
    policy_loader: Any | None = None,
    incubator: Any | None = None,
) -> tuple[str, str]:
    """Enforce vibe and domain mapping against declarative policy and sandbox incubator.

    Checks:
      1. Active candidate sandbox routes in RouteIncubator (FEAT-472).
      2. Hardcoded meta-lexicon detection (is_meta_lexicon).
      3. Validated declarative policy from TriagePolicyLoader (FEAT-467).
    """
    inc = incubator or _DEFAULT_INCUBATOR
    loader = policy_loader or _DEFAULT_POLICY_LOADER

    # 1. Check sandbox candidate routes
    if inc:
        try:
            candidates = inc.get_candidate_routes(active_only=True)
            q_lower = query.lower()
            for cand_name, cand_data in candidates.items():
                clean_name = cand_name.lower().replace("mouse_def:", "")
                if clean_name in q_lower:
                    return cand_name, cand_data.get("target_domain", "sandbox")
        except Exception:
            pass

    # 2. Check meta lexicon
    if is_meta_lexicon(query):
        return _META_DOMAIN_OVERRIDES["vibe"], _META_DOMAIN_OVERRIDES["domain"]

    # 3. WYWO standup briefing heuristic – detect before greeting since WYWO
    #    queries may contain words like "what's up" that overlap greetings.
    if _WYWO_RE.search(query):
        return "WYWO", "dream_stream"

    # 4. CASUAL greeting heuristic – colloquial pleasantries bypass LLM
    if _GREETING_RE.search(query):
        return "CASUAL", "standard"

    vibe = str(parsed_json.get("vibe", "CASUAL")).upper()
    domain = str(parsed_json.get("domain", "standard"))

    # 3. Check declarative policy loader
    if loader:
        rule = loader.get_vibe_rule(vibe)
        if rule and domain == "standard" and "target_domain" in rule:
            domain = rule["target_domain"]

    return vibe, domain


# ═══════════════════════════════════════════════════════════════════════════════
# 7. TriageEngine – Async Orchestration Shell
# ═══════════════════════════════════════════════════════════════════════════════

_TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "prereflection_triage_result",
        "schema": {
            "type": "object",
            "properties": {
                "inferred_intent": {"type": "string"},
                "addressed_to": {
                    "type": "string",
                    "enum": ["NONE", "BRAIN", "PINKY", "MICE"],
                },
                "vibe": {
                    "type": "string",
                    "enum": [
                        "TECHNICAL",
                        "CASUAL",
                        "HISTORICAL",
                        "ANALYTICAL",
                        "OPERATIONAL",
                        "FORENSIC",
                        "META",
                        "WYWO",
                        "SUPERVISORY",
                    ],
                },
                "domain": {
                    "type": "string",
                    "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard", "lab_history", "lab_internal", "dream_stream"],
                },
                "casual": {"type": "number"},
                "intrigue": {"type": "number"},
                "importance": {"type": "number"},
                "hyde_vector_text": {"type": "string"},
                "situation": {"type": "string"},
                "hints": {"type": "string"},
            },
            "required": [
                "inferred_intent",
                "addressed_to",
                "vibe",
                "domain",
                "casual",
                "intrigue",
                "importance",
                            ],
        },
    },
}

_BRAIN_PERSONA_SPEC: str = (
    "[PERSONA]: You are Deep Thought - the Brain's pre-conscious analytical stream. "
    "Sharing the Brain's right-hemisphere architecture, you are calm, strategic, "
    "and clinical; you synthesize pre-reflection vectors, technical telemetry, "
    "and system architecture before any character speaks."
)

_GREETING_SHORT_CIRCUIT: set[str] = {
    "hi",
    "hey",
    "hello",
    "what's up",
    "whats up",
    "good morning",
    "narf",
    "yo",
}

# ── Fast-path heuristic patterns ─────────────────────────────────────────
# CASUAL greeting regex: matches colloquial pleasantries that require no
# lab context and should bypass the heavy LLM classification prompt.
_GREETING_RE: re.Pattern[str] = re.compile(
    r"^(?:"
    r"how(?:'?re|'?s|\s+(?:are|is))\s+(?:things|you(?:rself)?(?:\s+doing)?|it\s+going|everything|life)\b|"
    r"what(?:'s|\s+is)\s+up\b|"
    r"good\s+(?:morning|afternoon|evening)\b|"
    r"hey|hi|hello|yo|howdy|sup|narf|what'?s\s+new"
    r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)

# WYWO standup briefing regex: matches queries requesting a summary of
# lab activity during user absence — 'While You Were Out' protocol.
_WYWO_RE: re.Pattern[str] = re.compile(
    r"(?:"
    r"what\s+(?:did\s+(?:you|the\s+lab)\s+)?(?:do|happen|go\s+on|transpire)\s+"
    r"(?:while\s+(?:i\s+)?(?:was\s+)?(?:out|away|gone|offline|sleeping|afk)|"
    r"since\s+(?:i|last))\b|"
    r"give\s+(?:me\s+)?(?:the\s+)?(?:stand[- ]?up|briefing|summary|update|recap|roundup)"
    r"(?:\s+(?:briefing|summary|update|recap|roundup))*\b|"
    r"(?:while\s+you\s+were\s+out|wywo)\s*(?:briefing|summary|update|recap)?\s*[.!?]?\s*$|"
    r"what\s+did\s+i\s+miss\b|"
    r"catch\s+me\s+up\b|"
    r"(?:what|happened)\s+while\s+i\s+was\s+(?:away|out|gone|offline|sleeping)\b"
    r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


class TriageEngine:
    """Stateless async triage orchestrator decoupled from CognitiveHub.

    Owns the pre-reflection schema, HyDE vector scrubbing, meta-lexicon
    override, and speaker sanitization.  The caller supplies a
    *resident_caller* that implements the ``call_tool("think", …)`` or
    native ``think()`` interface.

    Parameters
    ----------
    registry:
        Optional custom :class:`SpeakerRegistry`.  Uses the default lab
        roster when *None*.
    """

    def __init__(self, registry: SpeakerRegistry | None = None) -> None:
        self.registry = registry or SpeakerRegistry()
        self.speaker_registry = self.registry  # alias for external callers

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_triage_mode_context() -> str:
        """Build the system context block sent alongside the triage prompt."""
        return (
            "[MODE]: UNIFIED PRE-REFLECTION & TRIAGE\n"
            + _BRAIN_PERSONA_SPEC
            + "\n"
            "Translate user intent (I think the user is trying to say...).\n"
            "HyDE synthesis is gated by the 4-Domain HyDE Map Contract:\n"
            "  1. exp_tlm (Silicon Telemetry): PCIe error bursts, RAPL power/thermal caps.\n"
            "  2. exp_bkm (SRE playbooks): Point-of-failure playbooks, diagnostic shell BKMs.\n"
            "  3. exp_for (Forensic Logs): Kernel panic tracebacks, OOM crash logs.\n"
            "  4. lab_history (18-Year Archive): historical project notes (2005-2025).\n"
            "If the intent maps to a domain, synthesize a 3-part Composite HyDE Vector:\n"
            "[VALIDATION]: <term> | [STRATEGY]: <goal> | [SRE]: <bkm>\n"
            "If NOT mapped, set hyde_vector_text: \"\" and vibe: CASUAL."
        )

    @staticmethod
    def _bridge_signal_clean(raw_text: str) -> dict[str, Any] | None:
        """Parse the LLM triage output into a structured dict."""
        if not raw_text:
            return None

        if "{" not in raw_text:
            # Non-JSON prose fallback
            clean = raw_text.strip()
            if len(clean) > 15:
                return {
                    "inferred_intent": clean[:100],
                    "addressed_to": "PINKY",
                    "vibe": "CASUAL",
                    "domain": "standard",
                    "casual": 0.5,
                    "intrigue": 0.5,
                    "importance": 0.5,
                    "hyde_vector_text": clean,
                }
            return None

        # Multi-block JSON extractor (3B model resilience)
        json_blocks = re.findall(r"(\{.*?\})", raw_text, re.DOTALL)
        if not json_blocks:
            match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
            if match:
                json_blocks = [match.group(1)]
            else:
                return None

        for block in json_blocks:
            try:
                data = json.loads(block)
                if any(k in data for k in ("intent", "vibe", "addressed_to")):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    # ── resident_caller dispatch ──────────────────────────────────────────

    @staticmethod
    async def _invoke_resident(resident_caller: Any, prompt: str) -> str | None:
        """Invoke the resident LLM via call_tool, native think, or direct callable."""
        if resident_caller is None:
            return None

        try:
            if hasattr(resident_caller, "think") and callable(resident_caller.think):
                result = await resident_caller.think(prompt, internal=True)
                return result if isinstance(result, str) else str(result)

            if hasattr(resident_caller, "call_tool") and callable(resident_caller.call_tool):
                res = await resident_caller.call_tool(
                    "think",
                    {"prompt": prompt, "query": prompt},
                )
                if hasattr(res, "content") and res.content:
                    return res.content[0].text
                return str(res)

            if callable(resident_caller):
                result = await resident_caller(prompt)  # type: ignore[misc]
                return result if isinstance(result, str) else str(result)
        except Exception:  # noqa: BLE001 – resident failures must not propagate
            return None

        return None

    # ── public API ────────────────────────────────────────────────────────

    async def evaluate_triage(
        self,
        turn: str,
        history: list[dict[str, str]] | None = None,
        resident_caller: Any = None,
    ) -> dict[str, Any]:
        """Run the full pre-reflection triage pipeline.

        Parameters
        ----------
        turn:
            The raw user turn (may include speaker prefixes).
        history:
            Optional prior conversation turns for context.
        resident_caller:
            Async callable / MCP session that implements ``call_tool`` or
            ``think``.

        Returns
        -------
        A triage result dict with at least ``vibe``, ``domain``,
        ``addressed_to``, ``hyde_vector_text``, ``importance``,
        ``casual``, ``intrigue``.
        """
        # 1. Clean the incoming turn
        clean_turn = self.registry.sanitize(turn)

        # 1a. Fast-path: greeting heuristic skips the LLM entirely
        if _GREETING_RE.search(clean_turn):
            return {
                "inferred_intent": "greeting",
                "addressed_to": "PINKY",
                "vibe": "CASUAL",
                "domain": "standard",
                "casual": 0.95,
                "intrigue": 0.05,
                "importance": 0.1,
                "hyde_vector_text": "",
            }

        # 2. Build the mode context + conversation block
        mode_ctx = self._build_triage_mode_context()
        prompt = mode_ctx + "\n\n"
        if history:
            prompt += format_speaker_history(history) + "\n\n"
        prompt += f"User: {clean_turn}"

        # 3. Invoke the resident
        raw_output = await self._invoke_resident(resident_caller, prompt)

        # 4. Parse the LLM output
        parsed = self._bridge_signal_clean(raw_output or "")

        # 5. Fallback on parse failure
        if parsed is None:
            parsed = {
                "inferred_intent": "Parse failed – defaulting to casual.",
                "addressed_to": "PINKY",
                "vibe": "CASUAL",
                "domain": "standard",
                "casual": 0.5,
                "intrigue": 0.5,
                "importance": 0.5,
                "hyde_vector_text": "",
            }

        # 6. Meta-lexicon override
        vibe, domain = classify_vibe_and_domain(clean_turn, parsed)
        parsed["vibe"] = vibe
        parsed["domain"] = domain

        # 7. Scrub the HyDE vector
        raw_hyde = parsed.get("hyde_vector_text", "")
        parsed["hyde_vector_text"] = scrub_hyde_vector(raw_hyde)

        return parsed
