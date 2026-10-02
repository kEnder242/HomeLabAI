"""
[FEAT-632/633/634] Flywheel Closure: Tests for feedback telemetry endpoint.

Tests the /feedback and /attendant/feedback routes for human thumbs up/down telemetry.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

# Import the FoyerRouter from the correct path
from v5.foyer.router import FoyerRouter


class TestFoyerFeedback:
    """Test feedback telemetry endpoint."""

    def setup_method(self, method):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for FEEDBACK_LEDGER_PATH
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_path = Path(self.temp_dir) / "foyer_feedback_ledger.jsonl"

        # Monkeypatch the module-level FEEDBACK_LEDGER_PATH constant
        import v5.foyer.router as router_module
        self.original_feedback_ledger_path = router_module.FEEDBACK_LEDGER_PATH
        router_module.FEEDBACK_LEDGER_PATH = str(self.ledger_path)

        # Create a minimal aiohttp app with only handle_feedback
        self.app = web.Application()
        
        # Create a bare object to bind the handle_feedback method to
        bare_router = type('BareRouter', (), {})()
        bare_router.handle_feedback = FoyerRouter.handle_feedback.__get__(bare_router, FoyerRouter)
        
        # Add the route
        self.app.router.add_post("/feedback", bare_router.handle_feedback)
        self.app.router.add_post("/attendant/feedback", bare_router.handle_feedback)
        
        # Store bare_router for use in tests
        self.bare_router = bare_router

    def teardown_method(self, method):
        """Clean up after each test method."""
        # Restore original FEEDBACK_LEDGER_PATH
        import v5.foyer.router as router_module
        router_module.FEEDBACK_LEDGER_PATH = self.original_feedback_ledger_path

        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_feedback_success_up_and_down(self):
        """Test successful feedback submission for UP and DOWN ratings."""
        # Test UP rating
        request_up = make_mocked_request(
            'POST',
            '/feedback',
            headers={'Content-Type': 'application/json'},
            app=self.app,
            payload=json.dumps({"turn_id": "t1", "rating": "UP"}).encode()
        )
        
        # Add json() method to the request
        async def json_up():
            return {"turn_id": "t1", "rating": "UP"}
        request_up.json = json_up
        
        # Call handle_feedback directly
        response_up = await self.bare_router.handle_feedback(request_up)
        assert response_up.status == 200
        data_up = json.loads(response_up.text)
        assert data_up["status"] == "success"
        assert data_up["turn_id"] == "t1"
        assert data_up["rating"] == "UP"
        assert "ledger" in data_up
        assert "timestamp" in data_up

        # Test DOWN rating
        request_down = make_mocked_request(
            'POST',
            '/feedback',
            headers={'Content-Type': 'application/json'},
            app=self.app,
            payload=json.dumps({"turn_id": "t1", "rating": "DOWN"}).encode()
        )
        
        # Add json() method to the request
        async def json_down():
            return {"turn_id": "t1", "rating": "DOWN"}
        request_down.json = json_down
        
        response_down = await self.bare_router.handle_feedback(request_down)
        assert response_down.status == 200
        data_down = json.loads(response_down.text)
        assert data_down["status"] == "success"
        assert data_down["turn_id"] == "t1"
        assert data_down["rating"] == "DOWN"

        # Verify ledger file contains both entries
        assert self.ledger_path.exists()
        lines = self.ledger_path.read_text().strip().split("\n")
        assert len(lines) == 2

        # Parse and verify each record
        record1 = json.loads(lines[0])
        record2 = json.loads(lines[1])

        # Check first record (UP)
        assert record1["turn_id"] == "t1"
        assert record1["rating"] == "UP"
        assert "timestamp" in record1
        assert "notes" in record1

        # Check second record (DOWN)
        assert record2["turn_id"] == "t1"
        assert record2["rating"] == "DOWN"
        assert "timestamp" in record2
        assert "notes" in record2

    @pytest.mark.asyncio
    async def test_feedback_validation_errors(self):
        """Test feedback validation error cases."""
        # Create a bare object to bind the handle_feedback method to
        bare_router = type('BareRouter', (), {})()
        bare_router.handle_feedback = FoyerRouter.handle_feedback.__get__(bare_router, FoyerRouter)

        # Test missing turn_id
        request_no_turn = make_mocked_request(
            'POST',
            '/feedback',
            headers={'Content-Type': 'application/json'},
            app=self.app,
            payload=json.dumps({"rating": "UP"}).encode()
        )
        
        # Add json() method to the request
        async def json_no_turn():
            return {"rating": "UP"}
        request_no_turn.json = json_no_turn
        
        response_no_turn = await bare_router.handle_feedback(request_no_turn)
        assert response_no_turn.status == 400
        data_no_turn = json.loads(response_no_turn.text)
        assert data_no_turn["status"] == "ERROR"
        assert "'turn_id' is required" in data_no_turn["message"]

        # Test invalid rating
        request_invalid_rating = make_mocked_request(
            'POST',
            '/feedback',
            headers={'Content-Type': 'application/json'},
            app=self.app,
            payload=json.dumps({"turn_id": "x", "rating": "SIDEWAYS"}).encode()
        )
        
        # Add json() method to the request
        async def json_invalid_rating():
            return {"turn_id": "x", "rating": "SIDEWAYS"}
        request_invalid_rating.json = json_invalid_rating
        
        response_invalid_rating = await bare_router.handle_feedback(request_invalid_rating)
        assert response_invalid_rating.status == 400
        data_invalid_rating = json.loads(response_invalid_rating.text)
        assert data_invalid_rating["status"] == "ERROR"
        assert "'rating' must be UP or DOWN" in data_invalid_rating["message"]

        # Verify ledger file is empty (no valid records written)
        assert not self.ledger_path.exists() or self.ledger_path.read_text().strip() == ""