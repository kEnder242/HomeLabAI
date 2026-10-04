"""
Test suite for Story 98.3: Pre-Warmed Worker Session Resumption & Tool Blocking.

[FEAT-648] Verifies session ID reuse and sub-500ms dispatch latency.
"""
import time
from unittest.mock import patch, MagicMock

import pytest


class TestSessionResumption:
    """Test warm session resumption via delegate_story()."""

    def test_session_resumption_reuses_id(self):
        """Assert delegate_story(story_id="98.2", resume_session="sess-123") sends POST /session/sess-123/message."""
        from src.tests.delegate import delegate_story

        result = delegate_story(story_num="98.2", resume_session="sess-123")

        # Verify correct method and URL for session resumption
        assert result["method"] == "POST"
        assert result["url"] == "http://127.0.0.1:4097/session/sess-123/message"
        assert result["session_id"] == "sess-123"
        
        # Verify payload structure
        assert result["json"] is not None
        assert result["json"]["agent"] == "sisyphus-junior"
        assert "Resume story 98.2" in result["json"]["parts"][0]["text"]

    def test_session_latency_under_500ms(self):
        """Assert delegate_story returns in under 500ms (dispatch latency)."""
        from src.tests.delegate import delegate_story

        start = time.perf_counter()
        result = delegate_story(story_num="98.2", resume_session="sess-123")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.500, f"Dispatch latency {elapsed*1000:.1f}ms exceeds 500ms threshold"
        assert result["session_id"] == "sess-123"

    def test_warm_session_lookup_and_reuse(self):
        """Assert get_warm_session finds and returns registered session."""
        from v5.cognition.context_prewarmer import register_warm_session, get_warm_session

        # Clean up any existing test session
        import os
        test_path = "/tmp/active_warm_sessions.json"
        if os.path.exists(test_path):
            os.remove(test_path)

        try:
            # Register a warm session
            register_warm_session("sess-warm-456", "98.3", "sisyphus-junior")
            
            # Retrieve it
            warm_session = get_warm_session("98.3")
            
            assert warm_session == "sess-warm-456", f"Expected 'sess-warm-456', got '{warm_session}'"
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    def test_warm_session_fallback_creates_new(self):
        """Assert delegate_story creates new session when no warm session exists."""
        from src.tests.delegate import delegate_story
        import os

        # Clean up test file
        test_path = "/tmp/active_warm_sessions.json"
        if os.path.exists(test_path):
            os.remove(test_path)

        try:
            result = delegate_story(story_num="99.0", resume_session=None)
            
            # Should create a new session
            assert result["method"] == "POST"
            assert result["url"] == "http://127.0.0.1:4097/session"
            assert result["session_id"].startswith("sess-test-")
            assert result["json"]["directory"] == "/tmp"
            assert "Test session for story 99.0" in result["json"]["title"]
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    def test_warm_session_priority_over_fallback(self):
        """Assert warm session is preferred over creating new one when available."""
        from v5.cognition.context_prewarmer import register_warm_session
        from src.tests.delegate import delegate_story
        import os

        test_path = "/tmp/active_warm_sessions.json"
        if os.path.exists(test_path):
            os.remove(test_path)

        try:
            # Pre-register a warm session
            register_warm_session("sess-existing-789", "98.5", "sisyphus-junior")
            
            # Call without explicit resume_session - should reuse warm session
            result = delegate_story(story_num="98.5", resume_session=None)
            
            assert result["session_id"] == "sess-existing-789"
            assert result["url"] == "http://127.0.0.1:4097/session/sess-existing-789/message"
            assert "Continue story 98.5" in result["json"]["parts"][0]["text"]
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
