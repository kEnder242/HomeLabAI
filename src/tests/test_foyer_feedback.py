import pytest
import asyncio
import json
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "HomeLabAI" / "src"))

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Import the router module
import v5.foyer.router as router_mod
from v5.foyer.router import FoyerRouter


class _R:
    """Dummy class for binding handler methods."""
    pass


@pytest.fixture
def mock_feedback_ledger_path():
    """Create a temporary ledger file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        tmp_ledger_path = f.name
    
    yield tmp_ledger_path
    
    # Clean up
    if os.path.exists(tmp_ledger_path):
        os.unlink(tmp_ledger_path)


@pytest.fixture
def feedback_handler():
    """Create a feedback handler for testing."""
    dummy_obj = _R()
    handler = FoyerRouter.handle_feedback.__get__(dummy_obj, FoyerRouter)
    return handler


@pytest.fixture
def test_app(feedback_handler, mock_feedback_ledger_path):
    """Create a test app with the feedback handler."""
    # Monkey patch the FEEDBACK_LEDGER_PATH
    original_path = router_mod.FEEDBACK_LEDGER_PATH
    router_mod.FEEDBACK_LEDGER_PATH = mock_feedback_ledger_path
    
    try:
        # Create a minimal aiohttp app with just the feedback handler
        app = web.Application()
        app.router.add_post("/feedback", feedback_handler)
        
        yield app
    finally:
        # Restore the original path
        router_mod.FEEDBACK_LEDGER_PATH = original_path


@pytest.mark.asyncio
async def test_upvote_appends_ledger(test_app, mock_feedback_ledger_path):
    """Test that upvote appends to ledger correctly."""
    # Create test client
    async with TestClient(TestServer(test_app)) as client:
        # Make a POST request with upvote data
        response = await client.post(
            "/feedback",
            json={
                "rating": "UP",
                "query": "q1",
                "request_id": "r1",
                "response": "ok"
            }
        )
        
        # Verify response
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"
        assert data["rating"] == "UP"
        assert "latency_ms" in data
        assert data["latency_ms"] < 10  # Should be fast
        
        # Verify ledger file was created and contains the data
        with open(mock_feedback_ledger_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["rating"] == "UP"
            assert record["query"] == "q1"
            assert record["request_id"] == "r1"
            assert record["source"] == "UI"


@pytest.mark.asyncio
async def test_downvote_appends_ledger_and_foil(test_app, mock_feedback_ledger_path):
    """Test that downvote appends both main record and memory_foil record."""
    # Create test client
    async with TestClient(TestServer(test_app)) as client:
        # Make a POST request with downvote data
        response = await client.post(
            "/feedback",
            json={
                "rating": "DOWN",
                "query": "q2",
                "request_id": "r2",
                "response": "not good",
                "note": "bad response"
            }
        )
        
        # Verify response
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"
        assert data["rating"] == "DOWN"
        
        # Verify ledger file contains 2 lines: main record + memory_foil
        with open(mock_feedback_ledger_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            
            # First line should be the main record
            main_record = json.loads(lines[0])
            assert main_record["rating"] == "DOWN"
            assert main_record["query"] == "q2"
            assert main_record["request_id"] == "r2"
            assert main_record["source"] == "UI"
            assert main_record["user_note"] == "bad response"
            
            # Second line should be the memory_foil record
            foil_record = json.loads(lines[1])
            assert foil_record["type"] == "memory_foil"
            assert foil_record["request_id"] == "r2"
            assert foil_record["query"] == "q2"
            assert foil_record["note"] == "bad response"


@pytest.mark.asyncio
async def test_invalid_rating_rejected(test_app):
    """Test that invalid rating is rejected with 400 error."""
    # Create test client
    async with TestClient(TestServer(test_app)) as client:
        # Make a POST request with invalid rating
        response = await client.post(
            "/feedback",
            json={
                "rating": "MAYBE",
                "query": "q3",
                "request_id": "r3",
                "response": "test"
            }
        )
        
        # Verify response
        assert response.status == 400
        data = await response.json()
        assert data["status"] == "ERROR"
        assert "rating' must be UP or DOWN" in data["message"]