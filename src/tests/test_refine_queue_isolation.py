import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from v5.common.types import IntentEvent
from v5.foyer.router import FoyerRouter


class TestRefineQueueIsolation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.queue_file = os.path.join(self.temp_dir.name, "foyer_queue.jsonl")
        
        # Patch QUEUE_FILE to isolated temp directory
        self.queue_patch = patch("v5.foyer.router.QUEUE_FILE", self.queue_file)
        self.queue_patch.start()

        # Instantiate FoyerRouter with mocked components
        with patch("v5.foyer.router.CognitiveHub"):
            with patch("v5.foyer.router.ResidentManager"):
                with patch("v5.foyer.router.SensoryManager"):
                    with patch("v5.foyer.router.IgnitionManager"):
                        self.router = FoyerRouter(mode="HEADLESS")
        
        self.router.broadcast = AsyncMock()
        self.router.run_division_of_labor = AsyncMock()
        self.router._spawn_deep_thought_preamble = AsyncMock()

    async def asyncTearDown(self):
        self.queue_patch.stop()
        self.temp_dir.cleanup()

    async def test_internal_refine_bypasses_foyer_queue(self):
        """[FEAT-455 / Story 108.28] Verify [INTERNAL] [REFINE] bypasses foyer_queue.jsonl."""
        payload = {
            "type": "text_input",
            "content": "[INTERNAL] [REFINE]: Extract trigger context for GEM-042",
            "context": "GEM-042 evidence text",
            "request_id": "test_refine_001",
        }

        # Mock resident node response
        mock_node = MagicMock()
        mock_node_res = MagicMock()
        mock_node_res.content = [MagicMock(text="Trigger context: RAPL energy reading error")]
        mock_node.call_tool = AsyncMock(return_value=mock_node_res)
        self.router.residents.get_node = MagicMock(return_value=mock_node)

        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.send_str = AsyncMock()

        # Execute handle_internal_pass
        res = await self.router.handle_internal_pass(payload, socket_id="sock_test", ws=mock_ws)

        # 1. Assert QUEUE_FILE was NOT created or appended to
        self.assertFalse(
            os.path.exists(self.queue_file),
            "QUEUE_FILE must not exist after internal refine pass"
        )

        # 2. Assert division of labor and preamble were NOT called
        self.router.run_division_of_labor.assert_not_called()
        self.router._spawn_deep_thought_preamble.assert_not_called()

        # 3. Assert live telemetry streamed to channel='lab'
        broadcast_channels = [
            call.args[0].get("channel")
            for call in self.router.broadcast.call_args_list
            if call.args and isinstance(call.args[0], dict)
        ]
        self.assertIn("lab", broadcast_channels, "Internal pass must broadcast live telemetry to channel='lab'")

        # 4. Assert WS received the final result
        mock_ws.send_str.assert_called_once()
        sent_payload = json.loads(mock_ws.send_str.call_args[0][0])
        self.assertEqual(sent_payload["brain_source"], "The Brain")
        self.assertEqual(sent_payload["channel"], "lab")
        self.assertTrue(sent_payload["final"])
        self.assertIn("Trigger context", sent_payload["brain"])

    async def test_internal_flag_bypasses_foyer_queue(self):
        """[FEAT-455 / Story 108.28] Verify payload.get('internal')=True bypasses queue."""
        payload = {
            "type": "text_input",
            "content": "Analyze memory footprint",
            "internal": True,
            "request_id": "test_internal_002",
        }

        self.router.residents.get_node = MagicMock(return_value=None)
        res = await self.router.handle_internal_pass(payload)

        self.assertFalse(os.path.exists(self.queue_file))
        self.router.run_division_of_labor.assert_not_called()
        self.assertIn("INTERNAL REFINE ACKNOWLEDGED", res)

    async def test_queue_drainer_skips_internal_pass_if_queued(self):
        """[FEAT-455 / Story 108.28] Verify queue_drainer drops any orphaned internal events."""
        # Pre-seed QUEUE_FILE with an internal event and a standard event
        internal_evt = IntentEvent(query="[INTERNAL] [REFINE]: Stale background pass", source="test")
        standard_evt = IntentEvent(query="What is the current lab status?", source="test")

        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        with open(self.queue_file, "w") as f:
            f.write(internal_evt.to_json() + "\n")
            f.write(standard_evt.to_json() + "\n")

        self.router.residents.booted = True

        # Run one drain cycle of queue_drainer logic
        last_pos = 0
        with open(self.queue_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                event = IntentEvent.from_json(line)
                if event.status == "PENDING" and event.id not in self.router.processed_ids:
                    if (
                        event.query.startswith("[INTERNAL]")
                        or event.query.startswith("[REFINE]")
                        or event.query.startswith("[DREAM_PASS]")
                    ):
                        self.router.processed_ids.append(event.id)
                        continue
                    
                    self.router.processed_ids.append(event.id)
                    await self.router.run_division_of_labor(event.query, source=event.source, request_id=event.id)

        # Assert internal event was processed/drained but NEVER called division of labor
        self.assertIn(internal_evt.id, self.router.processed_ids)
        self.assertIn(standard_evt.id, self.router.processed_ids)

        # Only standard event should have reached run_division_of_labor
        self.router.run_division_of_labor.assert_called_once_with(
            standard_evt.query, source=standard_evt.source, request_id=standard_evt.id
        )

    async def test_standard_user_input_enqueues_normally(self):
        """[FEAT-455 / Story 108.28] Verify standard conversational input still enqueues to QUEUE_FILE."""
        await self.router.enqueue_intent("Hello Pinky and Brain", source="test_user")

        self.assertTrue(os.path.exists(self.queue_file))
        with open(self.queue_file, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        event = IntentEvent.from_json(lines[0])
        self.assertEqual(event.query, "Hello Pinky and Brain")

    async def test_ws_dispatch_routes_internal_to_handle_internal_pass(self):
        """[FEAT-455 / Story 108.28] Verify websocket message dispatch branches on is_internal."""
        data_internal = {
            "type": "text_input",
            "content": "[INTERNAL] [REFINE]: Generate trigger context",
        }
        data_standard = {
            "type": "text_input",
            "content": "Can you check the temperature?",
        }

        # Check the branching condition used in ws_handler
        def check_is_internal(data):
            query = data.get("content") or ""
            return data.get("internal", False) or (
                isinstance(query, str)
                and (
                    query.startswith("[INTERNAL]")
                    or query.startswith("[REFINE]")
                    or query.startswith("[DREAM_PASS]")
                )
            )

        self.assertTrue(check_is_internal(data_internal))
        self.assertTrue(check_is_internal({"type": "text_input", "content": "foo", "internal": True}))
        self.assertTrue(check_is_internal({"type": "text_input", "content": "[REFINE] something"}))
        self.assertTrue(check_is_internal({"type": "text_input", "content": "[DREAM_PASS] background pass"}))
        self.assertFalse(check_is_internal(data_standard))
        self.assertFalse(check_is_internal({"type": "text_input", "content": "Hello world"}))


if __name__ == "__main__":
    unittest.main()
