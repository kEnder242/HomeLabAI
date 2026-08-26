"""
[FEAT-470] Unit Tests for Pinky Critic Persona Satellite

Covers:
    1. build_critic_prompt – prompt construction, validation, dimensions
    2. parse_critic_payload – JSON parsing, embedded JSON, fallback
    3. format_chat_delivery – blending, robotic phrase stripping, prefix stripping
    4. format_crosstalk_telemetry – envelope structure
    5. Speaker prefix stripping – fallback and registry paths
    6. Edge cases – empty inputs, malformed data, boundary conditions
"""

from __future__ import annotations

import json

from nodes.pinky_critic_persona import (
    CriticResult,
    _BANNED_PHRASES,
    _build_fallback_stripper,
    _strip_speaker_prefix,
    build_critic_prompt,
    format_chat_delivery,
    format_crosstalk_telemetry,
    parse_critic_payload,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. build_critic_prompt
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildCriticPrompt:
    """Prompt construction for the Pinky Critic persona."""

    def test_returns_valid_json(self) -> None:
        """Output is valid JSON with required keys."""
        raw = build_critic_prompt("What is PCIe?", "PCIe is a bus.")
        data = json.loads(raw)
        assert "persona" in data
        assert "user_query" in data
        assert "technical_summary" in data
        assert "banned_phrases" in data
        assert "output_schema" in data

    def test_default_persona_name(self) -> None:
        """Default persona is Pinky."""
        data = json.loads(build_critic_prompt("q", "s"))
        assert data["persona"] == "Pinky"

    def test_custom_persona_name(self) -> None:
        """Custom persona overrides default."""
        data = json.loads(build_critic_prompt("q", "s", persona_name="Brain"))
        assert data["persona"] == "Brain"

    def test_default_dimensions(self) -> None:
        """Default critique dimensions include accuracy, tone, completeness."""
        data = json.loads(build_critic_prompt("q", "s"))
        assert "accuracy" in data["critique_dimensions"]
        assert "tone" in data["critique_dimensions"]
        assert "completeness" in data["critique_dimensions"]

    def test_custom_dimensions(self) -> None:
        """Custom dimensions override defaults."""
        dims = ["wit", "brevity"]
        data = json.loads(build_critic_prompt("q", "s", critique_dimensions=dims))
        assert data["critique_dimensions"] == dims

    def test_banned_phrases_included(self) -> None:
        """The banned phrases list is embedded in the prompt."""
        data = json.loads(build_critic_prompt("q", "s"))
        assert "A well-crafted response" in data["banned_phrases"]
        assert len(data["banned_phrases"]) >= 5

    def test_empty_query_raises(self) -> None:
        """Empty user_query raises ValueError."""
        try:
            build_critic_prompt("", "summary")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "user_query" in str(e)

    def test_whitespace_query_raises(self) -> None:
        """Whitespace-only user_query raises ValueError."""
        try:
            build_critic_prompt("   ", "summary")
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_empty_summary_raises(self) -> None:
        """Empty technical_summary raises ValueError."""
        try:
            build_critic_prompt("query", "")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "technical_summary" in str(e)

    def test_whitespace_summary_raises(self) -> None:
        """Whitespace-only technical_summary raises ValueError."""
        try:
            build_critic_prompt("query", "   \n  ")
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_input_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped from inputs."""
        data = json.loads(build_critic_prompt("  hello  ", "  world  "))
        assert data["user_query"] == "hello"
        assert data["technical_summary"] == "world"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. parse_critic_payload
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseCriticPayload:
    """LLM response parsing with resilience for malformed payloads."""

    def test_clean_json(self) -> None:
        """Well-formed JSON is parsed directly."""
        payload = json.dumps({
            "cartoon_retort": "Zort!",
            "critique_suggestions": ["Add more detail"],
        })
        result = parse_critic_payload(payload)
        assert result.cartoon_retort == "Zort!"
        assert result.critique_suggestions == ["Add more detail"]

    def test_embedded_json(self) -> None:
        """JSON embedded in surrounding prose is extracted."""
        raw = 'Here is my analysis:\n{"cartoon_retort": "Narf!", "critique_suggestions": ["Tone check"]}\nHope that helps!'
        result = parse_critic_payload(raw)
        assert result.cartoon_retort == "Narf!"
        assert "Tone check" in result.critique_suggestions

    def test_unparseable_fallback(self) -> None:
        """Completely unparseable text yields a fallback retort."""
        raw = "This is just free-form text with no JSON at all."
        result = parse_critic_payload(raw)
        assert result.cartoon_retort == raw[:200]
        assert "unstructured" in result.critique_suggestions[0].lower()

    def test_empty_input(self) -> None:
        """Empty string yields a safe default."""
        result = parse_critic_payload("")
        assert "blank" in result.cartoon_retort.lower()
        assert result.critique_suggestions == []

    def test_none_like_input(self) -> None:
        """Whitespace-only input yields a safe default."""
        result = parse_critic_payload("   \n  ")
        assert "blank" in result.cartoon_retort.lower()

    def test_missing_retort_key(self) -> None:
        """Missing cartoon_retort key yields a default string."""
        payload = json.dumps({"critique_suggestions": ["ok"]})
        result = parse_critic_payload(payload)
        assert "missing" in result.cartoon_retort.lower()

    def test_missing_suggestions_key(self) -> None:
        """Missing critique_suggestions key yields empty list."""
        payload = json.dumps({"cartoon_retort": "Hey!"})
        result = parse_critic_payload(payload)
        assert result.critique_suggestions == []

    def test_suggestions_not_a_list(self) -> None:
        """Non-list suggestions are coerced to a single-item list."""
        payload = json.dumps({
            "cartoon_retort": "Yo",
            "critique_suggestions": "single string suggestion",
        })
        result = parse_critic_payload(payload)
        assert result.critique_suggestions == ["single string suggestion"]

    def test_raw_dict_preserved(self) -> None:
        """The original dict is preserved in CriticResult.raw."""
        payload = json.dumps({"cartoon_retort": "X", "critique_suggestions": []})
        result = parse_critic_payload(payload)
        assert isinstance(result.raw, dict)
        assert result.raw.get("cartoon_retort") == "X"

    def test_non_dict_json_fallback(self) -> None:
        """A valid JSON array (not dict) triggers the fallback path."""
        result = parse_critic_payload('["not", "a", "dict"]')
        assert "not a dict" in result.cartoon_retort.lower() or len(result.cartoon_retort) > 0

    def test_coerce_result_with_telemetry_fields(self) -> None:
        """_coerce_result extracts score, reasoning, slop_found from JSON payload."""
        payload = json.dumps({
            "cartoon_retort": "Narf!",
            "critique_suggestions": ["Check thermals"],
            "score": 2,
            "reasoning": "Thermal throttling detected",
            "slop_found": True,
        })
        result = parse_critic_payload(payload)
        assert result.score == 2
        assert result.reasoning == "Thermal throttling detected"
        assert result.slop_found is True
        assert result.cartoon_retort == "Narf!"

    def test_coerce_result_missing_telemetry_defaults(self) -> None:
        """_coerce_result uses defaults when telemetry fields are missing."""
        payload = json.dumps({"cartoon_retort": "Yo"})
        result = parse_critic_payload(payload)
        assert result.score == 5
        assert result.reasoning == ""
        assert result.slop_found is False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. format_chat_delivery
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatChatDelivery:
    """Blending cartoon quips with technical summaries for chat output."""

    def test_basic_blend(self) -> None:
        """Retort and summary are joined with a blank line."""
        result = format_chat_delivery("Narf!", "The PCIe bus is stable.")
        assert result == "Narf!\n\nThe PCIe bus is stable."

    def test_strips_bracket_prefix_from_retort(self) -> None:
        """Leading [Pinky] prefix is stripped from the retort."""
        result = format_chat_delivery("[Pinky] Narf!", "Summary here.")
        assert result.startswith("Narf!")

    def test_strips_colon_prefix_from_retort(self) -> None:
        """Leading 'Brain:' prefix is stripped from the retort."""
        result = format_chat_delivery("Brain: Zort!", "Summary here.")
        assert result.startswith("Zort!")

    def test_strips_prefix_from_summary(self) -> None:
        """Leading speaker prefix is stripped from the summary too."""
        result = format_chat_delivery("Narf!", "[USER: Jason] The bus is fine.")
        assert "USER" not in result
        assert "The bus is fine." in result

    def test_banned_phrase_removed(self) -> None:
        """Default banned phrase 'A well-crafted response' is stripped."""
        raw = "A well-crafted response would be: everything is fine."
        result = format_chat_delivery(raw, "Summary.")
        assert "well-crafted" not in result.lower()
        assert "everything is fine" in result.lower()

    def test_banned_phrase_case_insensitive(self) -> None:
        """Banned phrase removal is case-insensitive."""
        raw = "HERE IS A WELL-CRAFTED RESPONSE for you."
        result = format_chat_delivery(raw, "Summary.")
        assert "well-crafted" not in result.lower()

    def test_custom_banned_phrases(self) -> None:
        """Custom banned phrase list replaces defaults."""
        result = format_chat_delivery(
            "Custom phrase here. Normal retort.",
            "Summary.",
            banned_phrases=["Custom phrase here"],
        )
        assert "Custom phrase" not in result
        assert "Normal retort" in result

    def test_empty_both_returns_empty(self) -> None:
        """Both inputs empty returns empty string."""
        assert format_chat_delivery("", "") == ""

    def test_empty_retort_returns_summary(self) -> None:
        """Empty retort returns just the summary."""
        result = format_chat_delivery("", "Only summary.")
        assert result == "Only summary."

    def test_empty_summary_returns_retort(self) -> None:
        """Empty summary returns just the retort."""
        result = format_chat_delivery("Only retort!", "")
        assert result == "Only retort!"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. format_crosstalk_telemetry
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatCrosstalkTelemetry:
    """Crosstalk telemetry envelope construction."""

    def test_envelope_structure(self) -> None:
        """Envelope contains all required keys."""
        result = format_crosstalk_telemetry(
            source_persona="Pinky",
            target_persona="Brain",
            payload={"cartoon_retort": "Yo"},
        )
        assert result["crosstalk"] is True
        assert result["source"] == "Pinky"
        assert result["target"] == "Brain"
        assert result["payload"]["cartoon_retort"] == "Yo"

    def test_optional_prompt_field(self) -> None:
        """Prompt and raw_response are optional."""
        result = format_crosstalk_telemetry(
            source_persona="Pinky",
            target_persona="Brain",
            payload={},
        )
        assert result["prompt"] == ""
        assert result["raw_response"] == ""

    def test_prompt_and_raw_response_populated(self) -> None:
        """Prompt and raw_response are stored when provided."""
        result = format_crosstalk_telemetry(
            source_persona="Pinky",
            target_persona="Brain",
            payload={},
            prompt="critique this",
            raw_response='{"cartoon_retort": "ok"}',
        )
        assert result["prompt"] == "critique this"
        assert "ok" in result["raw_response"]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Speaker prefix stripping (fallback path)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStripSpeakerPrefix:
    """Dynamic fallback prefix stripping when SpeakerRegistry is unavailable."""

    def test_bracket_prefix_stripped(self) -> None:
        """[Name] prefix is removed."""
        assert _strip_speaker_prefix("[Pinky] Hello") == "Hello"

    def test_bracket_with_role_stripped(self) -> None:
        """[ROLE: Name] prefix is removed."""
        assert _strip_speaker_prefix("[USER: Jason] Query") == "Query"

    def test_colon_prefix_stripped(self) -> None:
        """Name: prefix is removed."""
        assert _strip_speaker_prefix("Brain: Analysis") == "Analysis"

    def test_no_prefix_unchanged(self) -> None:
        """Text without prefix is returned unchanged."""
        assert _strip_speaker_prefix("Plain text here.") == "Plain text here."

    def test_fallback_stripper_regex(self) -> None:
        """The fallback stripper compiles successfully."""
        pat = _build_fallback_stripper()
        assert pat is not None
        assert pat.pattern  # Non-empty regex


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Edge cases & integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Cross-cutting edge cases and sanity checks."""

    def test_banned_phrases_list_not_empty(self) -> None:
        """The banned phrases list contains at least 5 entries."""
        assert len(_BANNED_PHRASES) >= 5

    def test_critique_result_dataclass(self) -> None:
        """CriticResult is a proper dataclass with defaults."""
        cr = CriticResult(cartoon_retort="test", critique_suggestions=[])
        assert cr.raw == {}

    def test_critique_result_defaults(self) -> None:
        """CriticResult has correct default values for new telemetry fields."""
        cr = CriticResult(cartoon_retort="Narf!", critique_suggestions=[])
        assert cr.score == 5
        assert cr.reasoning == ""
        assert cr.slop_found is False

    def test_critique_result_explicit_fields(self) -> None:
        """CriticResult accepts explicit score, reasoning, slop_found."""
        cr = CriticResult(
            cartoon_retort="Zort!",
            critique_suggestions=["Check VRAM"],
            score=3,
            reasoning="VRAM is tight",
            slop_found=True,
        )
        assert cr.score == 3
        assert cr.reasoning == "VRAM is tight"
        assert cr.slop_found is True

    def test_critique_result_retort_property(self) -> None:
        """CriticResult.retort property returns cartoon_retort."""
        cr = CriticResult(cartoon_retort="Hello", critique_suggestions=[])
        assert cr.retort == "Hello"
        assert cr.retort == cr.cartoon_retort

    def test_roundtrip_parse_format(self) -> None:
        """parse_critic_payload output feeds into format_chat_delivery."""
        payload = json.dumps({
            "cartoon_retort": "[Pinky] Zort! Everything checks out.",
            "critique_suggestions": ["Maybe add a chart"],
        })
        parsed = parse_critic_payload(payload)
        delivery = format_chat_delivery(parsed.cartoon_retort, "PCIe stable.")
        assert "Zort!" in delivery
        assert "PCIe stable." in delivery
        assert "Pinky" not in delivery  # prefix stripped

    def test_prompt_output_is_valid_json(self) -> None:
        """Every build_critic_prompt call produces parseable JSON."""
        for q, s in [("q1", "s1"), ("test query", "test summary"), ("a" * 100, "b" * 100)]:
            raw = build_critic_prompt(q, s)
            data = json.loads(raw)
            assert isinstance(data, dict)

    def test_format_delivery_strips_multiple_phrases(self) -> None:
        """Multiple banned phrases in the retort are all stripped."""
        raw = "Of course! A well-crafted response would be: done."
        result = format_chat_delivery(raw, "Summary.")
        assert "Of course" not in result
        assert "well-crafted" not in result.lower()
        assert "done." in result.lower()

    def test_parse_suggestions_with_none_values(self) -> None:
        """None values in suggestions list are filtered out."""
        payload = json.dumps({
            "cartoon_retort": "Hi",
            "critique_suggestions": ["valid", None, "", "also valid"],
        })
        result = parse_critic_payload(payload)
        assert "valid" in result.critique_suggestions
        assert "also valid" in result.critique_suggestions
        assert None not in result.critique_suggestions
        assert "" not in result.critique_suggestions
