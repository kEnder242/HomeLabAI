"""Unit tests for override_parser satellite (FEAT-145/REF-01)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.logic.override_parser import (
    is_override_query,
    parse_override_with_resident,
    save_override_to_file,
)


# ========================================================================
# 1. is_override_query
# ========================================================================


class TestIsOverrideQuery:
    """Detect GEM-xxxx / BKM-xxx override intents with correction keywords."""

    # --- Positive cases ---------------------------------------------------

    @pytest.mark.parametrize(
        "turn, expected_id",
        [
            ("GEM-0142 rank should be 5, update it", "GEM-0142"),
            ("BKM-022 is wrong here", "BKM-022"),
            ("Please fix GEM-1045 synopsis", "GEM-1045"),
            ("Override BKM-003 title to 'Safety'", "BKM-003"),
            ("Update GEM-0401 domain to security", "GEM-0401"),
            ("Change GEM-0099 rank to 3", "GEM-0099"),
        ],
        ids=[
            "gem-rank",
            "bkm-wrong",
            "gem-fix",
            "bkm-override",
            "gem-update",
            "gem-change",
        ],
    )
    def test_positive(self, turn: str, expected_id: str) -> None:
        matched, gem_id = is_override_query(turn)
        assert matched is True
        assert gem_id == expected_id

    # --- Prefix stripping -------------------------------------------------

    def test_me_prefix(self) -> None:
        matched, gem_id = is_override_query("[ME] GEM-0142 is wrong")
        assert matched is True
        assert gem_id == "GEM-0142"

    def test_user_prefix(self) -> None:
        matched, gem_id = is_override_query("[USER] fix BKM-010")
        assert matched is True
        assert gem_id == "BKM-010"

    def test_case_insensitive_prefix(self) -> None:
        matched, gem_id = is_override_query("[me] update GEM-0077")
        assert matched is True
        assert gem_id == "GEM-0077"

    # --- Negative cases ---------------------------------------------------

    @pytest.mark.parametrize(
        "turn",
        [
            "GEM-0142 looks good",        # no correction keyword
            "What is BKM-003?",           # question, not correction
            "Hello, how are you?",        # normal chat
            "Tell me about GEM-9999",     # no correction keyword
            "rank 5 is good",             # no gem/bkm id at all
            "[ME] nice weather today",    # prefix but no id
        ],
        ids=[
            "gem-positive-sentiment",
            "question-not-correction",
            "normal-chat",
            "tell-me-about",
            "no-id",
            "prefix-but-no-id",
        ],
    )
    def test_negative(self, turn: str) -> None:
        matched, gem_id = is_override_query(turn)
        assert matched is False
        assert gem_id is None


# ========================================================================
# 2. parse_override_with_resident
# ========================================================================


class TestParseOverrideWithResident:
    """Async resident-call parsing with JSON extraction and fallback."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    # --- Happy path -------------------------------------------------------

    def test_valid_json(self) -> None:
        async def fake_resident(prompt: str) -> str:
            return json.dumps({"rank": 5, "title": "Safety", "synopsis": "Best practices", "domain": "security"})

        result = self._run(
            parse_override_with_resident("GEM-0142", "override rank to 5", fake_resident)
        )
        assert result is not None
        assert result["rank"] == 5
        assert result["title"] == "Safety"
        assert result["domain"] == "security"

    def test_json_embedded_in_text(self) -> None:
        """Resident sometimes wraps JSON in chatter — still extractable."""

        async def fake_resident(prompt: str) -> str:
            return 'Sure! Here is the update: {"rank": 3, "title": null, "synopsis": "Updated", "domain": null}.'

        result = self._run(
            parse_override_with_resident("GEM-0077", "fix rank", fake_resident)
        )
        assert result is not None
        assert result["rank"] == 3
        assert result["synopsis"] == "Updated"

    def test_partial_keys(self) -> None:
        """Missing keys default to None."""

        async def fake_resident(prompt: str) -> str:
            return '{"rank": 2}'

        result = self._run(
            parse_override_with_resident("BKM-010", "change rank", fake_resident)
        )
        assert result is not None
        assert result["rank"] == 2
        assert result["title"] is None
        assert result["synopsis"] is None
        assert result["domain"] is None

    # --- Fallback / error paths -------------------------------------------

    def test_garbage_response(self) -> None:
        async def fake_resident(prompt: str) -> str:
            return "I don't understand. Let me try again..."

        result = self._run(
            parse_override_with_resident("GEM-0142", "fix title", fake_resident)
        )
        assert result is None

    def test_resident_exception(self) -> None:
        async def bad_resident(prompt: str) -> str:
            raise RuntimeError("model offline")

        result = self._run(
            parse_override_with_resident("GEM-0142", "fix title", bad_resident)
        )
        assert result is None

    def test_non_string_return(self) -> None:
        async def weird_resident(prompt: str) -> int:
            return 42  # type: ignore[return-value]

        result = self._run(
            parse_override_with_resident("GEM-0142", "fix title", weird_resident)
        )
        assert result is None

    def test_malformed_json(self) -> None:
        async def fake_resident(prompt: str) -> str:
            return '{"rank": 5, "title": unclosed'

        result = self._run(
            parse_override_with_resident("GEM-0142", "fix title", fake_resident)
        )
        assert result is None


# ========================================================================
# 3. save_override_to_file
# ========================================================================


class TestSaveOverrideToFile:
    """Atomic JSON persistence with BKM-022 compliance."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "overrides.json"
        ok = save_override_to_file("GEM-0142", {"rank": 5}, overrides_path=dest)
        assert ok is True
        assert dest.exists()

        data = json.loads(dest.read_text())
        assert data["overrides"]["GEM-0142"]["rank"] == 5

    def test_merges_into_existing(self, tmp_path: Path) -> None:
        dest = tmp_path / "overrides.json"
        dest.write_text(json.dumps({"overrides": {"GEM-0099": {"rank": 1}}}))

        ok = save_override_to_file("GEM-0142", {"rank": 5}, overrides_path=dest)
        assert ok is True

        data = json.loads(dest.read_text())
        assert data["overrides"]["GEM-0099"]["rank"] == 1  # untouched
        assert data["overrides"]["GEM-0142"]["rank"] == 5

    def test_updates_existing_gem(self, tmp_path: Path) -> None:
        dest = tmp_path / "overrides.json"
        dest.write_text(
            json.dumps({"overrides": {"GEM-0142": {"rank": 1, "title": "Old"}}})
        )

        ok = save_override_to_file("GEM-0142", {"rank": 5}, overrides_path=dest)
        assert ok is True

        data = json.loads(dest.read_text())
        assert data["overrides"]["GEM-0142"]["rank"] == 5
        assert data["overrides"]["GEM-0142"]["title"] == "Old"  # preserved

    def test_no_tmp_residue(self, tmp_path: Path) -> None:
        """After a successful write, no .tmp files should remain."""
        dest = tmp_path / "overrides.json"
        save_override_to_file("GEM-0142", {"rank": 3}, overrides_path=dest)

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_corrupt_existing_file(self, tmp_path: Path) -> None:
        """Corrupt JSON on disk should be replaced cleanly."""
        dest = tmp_path / "overrides.json"
        dest.write_text("NOT VALID JSON {{{")

        ok = save_override_to_file("GEM-0142", {"rank": 7}, overrides_path=dest)
        assert ok is True

        data = json.loads(dest.read_text())
        assert data["overrides"]["GEM-0142"]["rank"] == 7

    def test_default_path_expanduser(self, tmp_path: Path, monkeypatch) -> None:
        """Default path resolves with expanduser."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from src.logic import override_parser

        monkeypatch.setattr(
            override_parser,
            "_DEFAULT_OVERRIDES_PATH",
            fake_home / "Dev_Lab" / "Portfolio_Dev" / "field_notes" / "data" / "overrides.json",
        )

        ok = save_override_to_file("BKM-010", {"synopsis": "test"})
        assert ok is True

        target = fake_home / "Dev_Lab" / "Portfolio_Dev" / "field_notes" / "data" / "overrides.json"
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["overrides"]["BKM-010"]["synopsis"] == "test"
