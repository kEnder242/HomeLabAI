"""
[FEAT-467/468/471] Unit Tests for Decoupled Triage Engine Satellite

Covers:
    1. SpeakerRegistry - dynamic regex build, nested prefix sanitization
    2. extract_latest_user_query - multi-line, dirty prefixes
    3. format_speaker_history - structured turn formatting
    4. scrub_hyde_vector - angle-bracket stripping, edge cases
    5. is_meta_lexicon - keyword detection
    6. classify_vibe_and_domain - meta override, greeting fast-path, WYWO detection
    7. TriageEngine - async evaluate_triage end-to-end
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from src.logic.triage_engine import (
    SpeakerRegistry,
    classify_vibe_and_domain,
    extract_latest_user_query,
    format_speaker_history,
    is_meta_lexicon,
    scrub_hyde_vector,
    TriageEngine,
)


# ===========================================================================
# 1. SpeakerRegistry
# ===========================================================================


class TestSpeakerRegistry:
    """Dynamic regex builder and iterative prefix sanitizer."""

    def test_default_names_populated(self) -> None:
        """Default roster has all 10 standard names."""
        reg = SpeakerRegistry()
        assert len(reg.names) == 10
        assert "Pinky" in reg.names
        assert "Deep Thought" in reg.names

    def test_custom_names(self) -> None:
        """Custom name list overrides defaults."""
        reg = SpeakerRegistry(names=["Alice", "Bob"])
        assert reg.names == ["Alice", "Bob"]

    def test_strip_bracket_prefix(self) -> None:
        """Strip [Pinky] style bracket prefix."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[Pinky] Narf!") == "Narf!"

    def test_strip_bracket_with_colon_role(self) -> None:
        """Strip [USER: Jason] style bracket-with-role prefix."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[USER: Jason] Check the logs") == "Check the logs"

    def test_strip_colon_delimited_prefix(self) -> None:
        """Strip 'Brain:' style colon-delimited prefix."""
        reg = SpeakerRegistry()
        assert reg.sanitize("Brain: The root cause is clear.") == "The root cause is clear."

    def test_strip_case_insensitive(self) -> None:
        """Prefix matching is case-insensitive."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[pinky] narf") == "narf"
        assert reg.sanitize("brain: analysis") == "analysis"

    def test_nested_prefixes_stripped(self) -> None:
        """Multiple nested prefixes are iteratively removed."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[Pinky] Brain: Hello") == "Hello"

    def test_no_prefix_returns_clean(self) -> None:
        """Text without any prefix is returned unchanged."""
        reg = SpeakerRegistry()
        assert reg.sanitize("What is the PCIe error count?") == "What is the PCIe error count?"

    def test_empty_string(self) -> None:
        """Empty input returns empty string."""
        reg = SpeakerRegistry()
        assert reg.sanitize("") == ""

    def test_whitespace_only(self) -> None:
        """Whitespace-only input returns empty string."""
        reg = SpeakerRegistry()
        assert reg.sanitize("   \t  ") == ""

    def test_deep_thought_prefix(self) -> None:
        """Multi-word name 'Deep Thought' is properly escaped and matched."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[Deep Thought] Analysis complete.") == "Analysis complete."

    def test_unregistered_name_not_stripped(self) -> None:
        """Unknown name prefix is not stripped."""
        reg = SpeakerRegistry()
        assert reg.sanitize("Zorp: Hello there") == "Zorp: Hello there"

    def test_me_prefix(self) -> None:
        """'Me' is in the default registry."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[Me] I need help") == "I need help"

    def test_system_prefix(self) -> None:
        """System prefix is stripped."""
        reg = SpeakerRegistry()
        assert reg.sanitize("[System] Status update") == "Status update"


# ===========================================================================
# 2. extract_latest_user_query
# ===========================================================================


class TestExtractLatestUserQuery:
    """Extract the latest user command from raw turn or history."""

    def test_single_line_no_prefix(self) -> None:
        """Simple query without prefix is returned as-is."""
        assert extract_latest_user_query("What is the lab status?") == "What is the lab status?"

    def test_single_line_with_me_prefix(self) -> None:
        """[ME] prefix is stripped."""
        assert extract_latest_user_query("[ME] Check the sweeper") == "Check the sweeper"

    def test_multi_line_returns_last(self) -> None:
        """Multi-line input returns the last non-empty line, cleaned."""
        text = "[Brain] Context line\n[ME] What is the audio pipeline status?"
        assert extract_latest_user_query(text) == "What is the audio pipeline status?"

    def test_empty_string(self) -> None:
        """Empty input returns empty string."""
        assert extract_latest_user_query("") == ""

    def test_none_like_input(self) -> None:
        """Whitespace-only returns empty."""
        assert extract_latest_user_query("  \n  \n  ") == ""

    def test_user_bracket_prefix(self) -> None:
        """[USER] prefix is stripped."""
        assert extract_latest_user_query("[USER] Show maintenance logs") == "Show maintenance logs"

    def test_user_colon_prefix(self) -> None:
        """User: prefix is stripped."""
        assert extract_latest_user_query("User: Show maintenance logs") == "Show maintenance logs"


# ===========================================================================
# 3. format_speaker_history
# ===========================================================================


class TestFormatSpeakerHistory:
    """Structured speaker-tagged turn formatting."""

    def test_basic_user_assistant(self) -> None:
        """User + assistant turns get correct tags."""
        turns = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = format_speaker_history(turns)
        assert result == "[USER] Hello\n[ASSISTANT] Hi there"

    def test_named_speaker(self) -> None:
        """Optional name field is included in the tag."""
        turns = [
            {"role": "user", "name": "Jason", "content": "Status?"},
            {"role": "assistant", "name": "Brain", "content": "Nominal."},
        ]
        result = format_speaker_history(turns)
        assert "[USER: Jason] Status?" in result
        assert "[ASSISTANT: Brain] Nominal." in result

    def test_empty_history(self) -> None:
        """Empty list returns empty string."""
        assert format_speaker_history([]) == ""

    def test_system_role(self) -> None:
        """System role gets SYSTEM tag."""
        turns = [{"role": "system", "content": "Boot complete"}]
        assert format_speaker_history(turns) == "[SYSTEM] Boot complete"

    def test_unknown_role_fallback(self) -> None:
        """Unknown role uppercased as-is."""
        turns = [{"role": "critic", "content": "Needs work"}]
        assert format_speaker_history(turns) == "[CRITIC] Needs work"

    def test_strips_content_whitespace(self) -> None:
        """Content is .strip()ed per turn."""
        turns = [{"role": "user", "content": "  spaced  "}]
        assert format_speaker_history(turns) == "[USER] spaced"


# ===========================================================================
# 4. scrub_hyde_vector
# ===========================================================================


class TestScrubHydeVector:
    """Template angle-bracket stripping for HyDE vectors."""

    def test_strip_single_placeholder(self) -> None:
        """Single angle-bracket placeholder is removed."""
        result = scrub_hyde_vector("[VALIDATION]: <silicon_term> | [STRATEGY]: goal")
        assert "<silicon_term>" not in result
        assert "[VALIDATION]:" in result
        assert "goal" in result

    def test_strip_multiple_placeholders(self) -> None:
        """All angle-bracket placeholders are removed."""
        result = scrub_hyde_vector("[VALIDATION]: <term> | [STRATEGY]: <goal> | [SRE]: <bkm>")
        assert "<term>" not in result
        assert "<goal>" not in result
        assert "<bkm>" not in result
        assert "[VALIDATION]:" in result

    def test_clean_text_unchanged(self) -> None:
        """Text without angle brackets passes through unchanged."""
        vec = "[VALIDATION]: PCIe AER | [STRATEGY]: improve throughput"
        assert scrub_hyde_vector(vec) == vec

    def test_empty_string(self) -> None:
        """Empty input returns empty string."""
        assert scrub_hyde_vector("") == ""

    def test_none_input(self) -> None:
        """None input returns empty string."""
        assert scrub_hyde_vector(None) == ""  # type: ignore[arg-type]

    def test_only_placeholders_returns_empty(self) -> None:
        """If only placeholders remain after stripping -> empty (Zero Context)."""
        assert scrub_hyde_vector("<silicon_term_or_pcie_ras>") == ""

    def test_empty_after_strip(self) -> None:
        """Whitespace-only placeholder content returns empty."""
        assert scrub_hyde_vector("  <>  ") == ""

    def test_nested_brackets_stripped(self) -> None:
        """Nested angle brackets like <foo<bar>> are stripped."""
        result = scrub_hyde_vector("text <inner<nested>> done")
        assert "<inner<nested>>" not in result
        assert "text" in result
        assert "done" in result

    def test_mixed_clean_and_placeholder(self) -> None:
        """Mix of real content and placeholders preserves the real content."""
        result = scrub_hyde_vector("Fix <placeholder> now")
        assert result == "Fix now"

    def test_non_string_returns_empty(self) -> None:
        """Non-string input returns empty string."""
        assert scrub_hyde_vector(42) == ""  # type: ignore[arg-type]


# ===========================================================================
# 5. is_meta_lexicon
# ===========================================================================


class TestIsMetaLexicon:
    """Live lab module keyword detection."""

    def test_audio_pipeline_detected(self) -> None:
        """audio_pipeline keyword triggers meta."""
        assert is_meta_lexicon("What is the audio_pipeline status?") is True

    def test_maintenance_sweeper_detected(self) -> None:
        """maintenance_sweeper keyword triggers meta."""
        assert is_meta_lexicon("Run the maintenance_sweeper now") is True

    def test_override_parser_detected(self) -> None:
        """override_parser keyword triggers meta."""
        assert is_meta_lexicon("Check override_parser behavior") is True

    def test_foyer_detected(self) -> None:
        """foyer keyword triggers meta."""
        assert is_meta_lexicon("How is the foyer router?") is True

    def test_vllm_detected(self) -> None:
        """vllm keyword triggers meta."""
        assert is_meta_lexicon("vllm is running slow") is True

    def test_attendant_detected(self) -> None:
        """attendant keyword triggers meta."""
        assert is_meta_lexicon("The attendant needs a restart") is True

    def test_residents_detected(self) -> None:
        """residents keyword triggers meta."""
        assert is_meta_lexicon("Which residents are active?") is True

    def test_features_detected(self) -> None:
        """features keyword triggers meta."""
        assert is_meta_lexicon("List all active features") is True

    def test_bkm_detected(self) -> None:
        """bkm keyword triggers meta."""
        assert is_meta_lexicon("Which BKM applies here?") is True

    def test_no_match(self) -> None:
        """Normal technical query does not match."""
        assert is_meta_lexicon("What is the PCIe AER error count?") is False

    def test_empty_string(self) -> None:
        """Empty query returns False."""
        assert is_meta_lexicon("") is False

    def test_none_like(self) -> None:
        """Whitespace-only returns False."""
        assert is_meta_lexicon("   ") is False

    def test_partial_word_match(self) -> None:
        """Substring within a token still matches (token-level via regex)."""
        assert is_meta_lexicon("restarting the vllm server") is True

    def test_uppercase_keywords(self) -> None:
        """Matching is case-insensitive via lowercasing."""
        assert is_meta_lexicon("Check the VLLM status") is True
        assert is_meta_lexicon("Check the ATTENDANT status") is True


# ===========================================================================
# 6. classify_vibe_and_domain
# ===========================================================================


class TestClassifyVibeAndDomain:
    """Meta-lexicon override, greeting fast-path, and WYWO detection."""

    def test_meta_override(self) -> None:
        """Meta keyword -> vibe=META, domain=lab_internal regardless of parsed."""
        vibe, domain = classify_vibe_and_domain(
            "What is the audio_pipeline status?",
            {"vibe": "TECHNICAL", "domain": "exp_tlm"},
        )
        assert vibe == "META"
        assert domain == "lab_internal"

    def test_passthrough_no_meta(self) -> None:
        """No meta keyword -> parsed values pass through."""
        vibe, domain = classify_vibe_and_domain(
            "Check RAPL msr on node 2",
            {"vibe": "TECHNICAL", "domain": "exp_tlm"},
        )
        assert vibe == "TECHNICAL"
        assert domain == "exp_tlm"

    def test_greeting_semantic_passthrough(self) -> None:
        """Semantic greeting parsed values pass through without mutation."""
        vibe, domain = classify_vibe_and_domain(
            "how are things?",
            {"vibe": "CASUAL", "domain": "unknown"},
        )
        assert vibe == "CASUAL"
        assert domain == "unknown"

    def test_wywo_semantic_passthrough(self) -> None:
        """Semantic WYWO parsed values pass through without mutation."""
        vibe, domain = classify_vibe_and_domain(
            "what did you do while I was out?",
            {"vibe": "WYWO", "domain": "dream_stream"},
        )
        assert vibe == "WYWO"
        assert domain == "dream_stream"

    def test_wywo_what_happened_while_away(self) -> None:
        """'what happened while I was away?' -> WYWO, dream_stream when parsed."""
        vibe, domain = classify_vibe_and_domain(
            "what happened while I was away?",
            {"vibe": "WYWO", "domain": "dream_stream"},
        )
        assert vibe == "WYWO"
        assert domain == "dream_stream"

    def test_wywo_catch_me_up(self) -> None:
        """'catch me up' -> WYWO, dream_stream when parsed."""
        vibe, domain = classify_vibe_and_domain(
            "catch me up",
            {"vibe": "WYWO", "domain": "dream_stream"},
        )
        assert vibe == "WYWO"
        assert domain == "dream_stream"

    def test_wywo_while_you_were_out(self) -> None:
        """'while you were out' -> WYWO, dream_stream when parsed."""
        vibe, domain = classify_vibe_and_domain(
            "while you were out",
            {"vibe": "WYWO", "domain": "dream_stream"},
        )
        assert vibe == "WYWO"
        assert domain == "dream_stream"

    def test_wywo_what_did_i_miss(self) -> None:
        """'what did I miss?' -> WYWO, dream_stream when parsed."""
        vibe, domain = classify_vibe_and_domain(
            "what did I miss?",
            {"vibe": "WYWO", "domain": "dream_stream"},
        )
        assert vibe == "WYWO"
        assert domain == "dream_stream"

    def test_empty_parsed_defaults(self) -> None:
        """Empty parsed_json falls back to CASUAL/standard for non-matching query."""
        vibe, domain = classify_vibe_and_domain("some random text", {})
        assert vibe == "CASUAL"
        assert domain == "standard"

    def test_meta_with_vllm(self) -> None:
        """vllm keyword overrides even when parsed says HISTORICAL."""
        vibe, domain = classify_vibe_and_domain(
            "The vllm model swap failed",
            {"vibe": "HISTORICAL", "domain": "lab_history"},
        )
        assert vibe == "META"
        assert domain == "lab_internal"

    def test_technical_query_passthrough(self) -> None:
        """Genuine technical query passes through to LLM classification."""
        vibe, domain = classify_vibe_and_domain(
            "check RAPL msr on node 2",
            {"vibe": "TECHNICAL", "domain": "exp_tlm"},
        )
        assert vibe == "TECHNICAL"
        assert domain == "exp_tlm"

    def test_forensic_query_passthrough(self) -> None:
        """Genuine forensic query passes through to LLM classification."""
        vibe, domain = classify_vibe_and_domain(
            "show me the kernel panic traceback from last boot",
            {"vibe": "FORENSIC", "domain": "exp_for"},
        )
        assert vibe == "FORENSIC"
        assert domain == "exp_for"

    def test_operational_query_passthrough(self) -> None:
        """Genuine operational query passes through to LLM classification."""
        vibe, domain = classify_vibe_and_domain(
            "run the OOM kill recovery playbook",
            {"vibe": "OPERATIONAL", "domain": "exp_bkm"},
        )
        assert vibe == "OPERATIONAL"
        assert domain == "exp_bkm"


# ===========================================================================
# 7. TriageEngine - Async evaluate_triage
# ===========================================================================


class _MockResident:
    """Simulates a resident LLM that returns pre-canned JSON."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def think(self, prompt: str, internal: bool = False) -> str:
        return self._response


class _MockResidentWithTool:
    """Simulates a resident that uses call_tool('think', ...)."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MagicMock:
        result = MagicMock()
        result.content = [MagicMock(text=self._response)]
        return result


class TestTriageEngine:
    """End-to-end async triage pipeline tests."""

    def test_evaluate_triage_native_think(self) -> None:
        """Resident with native think() returns parsed triage."""
        triage_json = (
            '{"inferred_intent": "check lab", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "standard", "casual": 0.8, '
            '"intrigue": 0.2, "importance": 0.3, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage("[Pinky] Hello Pinky", resident_caller=resident)
        )

        assert result["vibe"] == "CASUAL"
        assert result["addressed_to"] == "PINKY"

    def test_evaluate_triage_call_tool(self) -> None:
        """Resident with call_tool('think', ...) interface."""
        triage_json = (
            '{"inferred_intent": "error analysis", "addressed_to": "BRAIN", '
            '"vibe": "TECHNICAL", "domain": "exp_tlm", "casual": 0.2, '
            '"intrigue": 0.7, "importance": 0.8, "hyde_vector_text": "[VALIDATION]: PCIe AER"}'
        )
        resident = _MockResidentWithTool(triage_json)
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage("Check PCIe AER error count", resident_caller=resident)
        )

        assert result["vibe"] == "TECHNICAL"
        assert result["domain"] == "exp_tlm"

    def test_evaluate_triage_meta_override(self) -> None:
        """Meta-lexicon in query overrides LLM triage output."""
        triage_json = (
            '{"inferred_intent": "check system", "addressed_to": "BRAIN", '
            '"vibe": "TECHNICAL", "domain": "exp_tlm", "casual": 0.2, '
            '"intrigue": 0.5, "importance": 0.5, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage(
                "What is the audio_pipeline status?",
                resident_caller=resident,
            )
        )

        assert result["vibe"] == "META"
        assert result["domain"] == "lab_internal"

    def test_evaluate_triage_hyde_scrubbed(self) -> None:
        """HyDE vector angle brackets are scrubbed from output."""
        triage_json = (
            '{"inferred_intent": "analysis", "addressed_to": "BRAIN", '
            '"vibe": "TECHNICAL", "domain": "exp_tlm", "casual": 0.1, '
            '"intrigue": 0.7, "importance": 0.8, '
            '"hyde_vector_text": "[VALIDATION]: <silicon_term_or_pcie_ras> | [STRATEGY]: goal"}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage("Analyze PCIe errors on node 1", resident_caller=resident)
        )

        assert "<silicon_term_or_pcie_ras>" not in result["hyde_vector_text"]
        assert "[VALIDATION]:" in result["hyde_vector_text"]

    def test_evaluate_triage_none_resident_fallback(self) -> None:
        """None resident_caller produces fallback triage."""
        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage("Check lab status", resident_caller=None)
        )
        assert result["vibe"] == "CASUAL"
        assert result["addressed_to"] == "NONE"

    def test_evaluate_triage_history_formatted(self) -> None:
        """History turns are included in the prompt (smoke test)."""
        triage_json = (
            '{"inferred_intent": "follow-up", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "standard", "casual": 0.5, '
            '"intrigue": 0.3, "importance": 0.3, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()
        history = [
            {"role": "user", "name": "Jason", "content": "Earlier question"},
            {"role": "assistant", "name": "Pinky", "content": "Earlier answer"},
        ]

        result = asyncio.run(
            engine.evaluate_triage("Follow-up question", history=history, resident_caller=resident)
        )

        assert result["vibe"] == "CASUAL"

    def test_evaluate_triage_dirty_prefix_stripped(self) -> None:
        """Dirty [ME] prefix on the turn is stripped before triage."""
        triage_json = (
            '{"inferred_intent": "check status", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "standard", "casual": 0.5, '
            '"intrigue": 0.3, "importance": 0.3, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage("[ME] Check the lab status", resident_caller=resident)
        )

        assert result is not None
        assert "vibe" in result

    def test_evaluate_triage_fallback_on_bad_json(self) -> None:
        """Garbage LLM output triggers fallback triage."""
        resident = _MockResident("This is not JSON at all, just random gibberish text")
        engine = TriageEngine()

        result = asyncio.run(
            engine.evaluate_triage("Check lab status", resident_caller=resident)
        )

        # Should get a fallback with CASUAL vibe and NONE entity targeting
        assert result["vibe"] == "CASUAL"
        assert result["addressed_to"] == "NONE"

    def test_evaluate_triage_callable_resident(self) -> None:
        """Raw async callable as resident_caller works."""
        triage_json = (
            '{"inferred_intent": "test", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "standard", "casual": 0.5, '
            '"intrigue": 0.3, "importance": 0.3, "hyde_vector_text": ""}'
        )

        async def _mock_resident(prompt: str) -> str:
            return triage_json

        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage("Test query", resident_caller=_mock_resident)
        )
        assert result["vibe"] == "CASUAL"

    def test_registry_alias(self) -> None:
        """speaker_registry attribute is accessible."""
        engine = TriageEngine()
        assert engine.speaker_registry is engine.registry

    def test_custom_registry(self) -> None:
        """Custom registry is used for sanitization."""
        reg = SpeakerRegistry(names=["CustomBot"])
        engine = TriageEngine(registry=reg)
        assert engine.registry.sanitize("[CustomBot] Hello") == "Hello"


# ===========================================================================
# 8. Semantic Greeting Evaluation (evaluate_triage)
# ===========================================================================


class TestGreetingSemanticEvaluation:
    """Greeting queries are semantically classified via resident model."""

    def test_greeting_how_are_things(self) -> None:
        """'how are things?' returns CASUAL via mock resident."""
        triage_json = (
            '{"inferred_intent": "greeting", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "unknown", "casual": 0.9, '
            '"intrigue": 0.1, "importance": 0.1, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage("how are things?", resident_caller=resident)
        )
        assert result["vibe"] == "CASUAL"
        assert result["domain"] == "unknown"
        assert result["importance"] == 0.1
        assert result["hyde_vector_text"] == ""

    def test_greeting_hello(self) -> None:
        """'hello' returns CASUAL via mock resident."""
        triage_json = (
            '{"inferred_intent": "greeting", "addressed_to": "PINKY", '
            '"vibe": "CASUAL", "domain": "unknown", "casual": 0.9, '
            '"intrigue": 0.1, "importance": 0.1, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage("hello", resident_caller=resident)
        )
        assert result["vibe"] == "CASUAL"
        assert result["addressed_to"] == "PINKY"


# ===========================================================================
# 9. WYWO Standup Briefing (evaluate_triage)
# ===========================================================================


class TestWYWOClassification:
    """WYWO queries are classified via semantic resident model."""

    def test_wywo_what_did_you_do_while_i_was_out(self) -> None:
        """'what did you do while I was out?' -> WYWO."""
        triage_json = (
            '{"inferred_intent": "wywo", "addressed_to": "PINKY", '
            '"vibe": "WYWO", "domain": "dream_stream", "casual": 0.5, '
            '"intrigue": 0.5, "importance": 0.6, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage(
                "what did you do while I was out?",
                resident_caller=resident,
            )
        )
        assert result["vibe"] == "WYWO"
        assert result["domain"] == "dream_stream"

    def test_wywo_give_me_the_briefing(self) -> None:
        """'give me the briefing' -> WYWO."""
        triage_json = (
            '{"inferred_intent": "wywo", "addressed_to": "PINKY", '
            '"vibe": "WYWO", "domain": "dream_stream", "casual": 0.5, '
            '"intrigue": 0.5, "importance": 0.6, "hyde_vector_text": ""}'
        )
        resident = _MockResident(triage_json)
        engine = TriageEngine()
        result = asyncio.run(
            engine.evaluate_triage("give me the briefing", resident_caller=resident)
        )
        assert result["vibe"] == "WYWO"
        assert result["domain"] == "dream_stream"
