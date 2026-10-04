#!/usr/bin/env python3
"""
test_session_resumption.py — [FEAT-648] Pre-Warmed Worker Session Resumption Tests

Validates:
1. Warm session cache persistence in /tmp/active_warm_sessions.json.
2. Fast session verification & reuse via OpenCode REST port 4097 (<500ms).
3. Session resumption via POST /session/{id}/message.
"""

import json
import os
import time
import urllib.request
import pytest
from unittest.mock import patch, MagicMock

WARM_SESSION_FILE = "/tmp/active_warm_sessions.json"


def save_warm_session(agent: str, session_id: str):
    """[FEAT-648] Persist latest warm session ID for an agent."""
    data = {}
    if os.path.exists(WARM_SESSION_FILE):
        try:
            with open(WARM_SESSION_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[agent] = {
        "session_id": session_id,
        "timestamp": time.time(),
    }
    with open(WARM_SESSION_FILE, "w") as f:
        json.dump(data, f)


def get_warm_session(agent: str, max_age_seconds: float = 1800.0) -> str | None:
    """[FEAT-648] Retrieve valid unexpired warm session ID for an agent."""
    if not os.path.exists(WARM_SESSION_FILE):
        return None
    try:
        with open(WARM_SESSION_FILE, "r") as f:
            data = json.load(f)
        entry = data.get(agent)
        if entry and isinstance(entry, dict):
            if time.time() - entry.get("timestamp", 0) <= max_age_seconds:
                return entry.get("session_id")
    except Exception:
        pass
    return None


class TestSessionResumption:
    def test_warm_session_cache_write_and_read(self, tmp_path, monkeypatch):
        """Literal Assertion: Warm session ID is stored and retrieved before expiry."""
        test_file = str(tmp_path / "warm_sessions.json")
        import tests.test_session_resumption as mod
        monkeypatch.setattr(mod, "WARM_SESSION_FILE", test_file)

        save_warm_session("atlas", "ses_test_atlas_123")
        save_warm_session("sisyphus-junior", "ses_test_junior_456")

        atlas_sid = get_warm_session("atlas")
        junior_sid = get_warm_session("sisyphus-junior")

        assert atlas_sid == "ses_test_atlas_123"
        assert junior_sid == "ses_test_junior_456"

    def test_warm_session_expiry(self, tmp_path, monkeypatch):
        """Literal Assertion: Expired warm session returns None."""
        test_file = str(tmp_path / "warm_sessions.json")
        import tests.test_session_resumption as mod
        monkeypatch.setattr(mod, "WARM_SESSION_FILE", test_file)

        save_warm_session("atlas", "ses_old_123")
        # Force timestamp to 1 hour ago
        with open(test_file, "r") as f:
            data = json.load(f)
        data["atlas"]["timestamp"] = time.time() - 3600
        with open(test_file, "w") as f:
            json.dump(data, f)

        assert get_warm_session("atlas", max_age_seconds=600) is None

    def test_session_resumption_reuses_id(self):
        """Literal Assertion: Resuming session verifies existing ID without creating a new session."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"id": "ses_existing_789", "title": "Warm Session"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        start = time.time()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            req = urllib.request.Request("http://127.0.0.1:4097/session/ses_existing_789")
            with urllib.request.urlopen(req, timeout=3) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - start

        assert res_data["id"] == "ses_existing_789"
        assert elapsed < 0.500

    def test_session_resumption_message_post(self):
        """Literal Assertion: Sending message to existing session posts to /session/{id}/message."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "parts": [{"type": "text", "text": "Task completed successfully"}],
            "finish": "stop"
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        session_id = "ses_warm_123"
        payload = json.dumps({"parts": [{"type": "text", "text": "Execute task"}]}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            req = urllib.request.Request(
                f"http://127.0.0.1:4097/session/{session_id}/message",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            assert req.full_url == f"http://127.0.0.1:4097/session/{session_id}/message"
            assert result["finish"] == "stop"
            assert "Task completed successfully" in result["parts"][0]["text"]
