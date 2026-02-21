import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from nodes.loader import BicameralNode

class TestFederatedFailover(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.node = BicameralNode("Brain", "Test Prompt")

    @patch("nodes.loader.resolve_ip")
    @patch("aiohttp.ClientSession.get")
    async def test_kender_offline_fallback_to_local(self, mock_get, mock_resolve):
        """Verify that if KENDER is offline, we fallback to local engines."""
        mock_resolve.return_value = "192.168.1.26"
        
        # 1. First call (KENDER) raises an exception
        # 2. Second call (Local vLLM) succeeds
        mock_response_ok = AsyncMock()
        mock_response_ok.status = 200
        
        # side_effect for session.get
        # We need to return an AsyncContextManager
        class MockContextManager:
            def __init__(self, side_effect=None, return_value=None):
                self.side_effect = side_effect
                self.return_value = return_value
            async def __aenter__(self):
                if self.side_effect: raise self.side_effect
                return self.return_value
            async def __aexit__(self, *args): pass

        mock_get.side_effect = [
            MockContextManager(side_effect=Exception("Connection Refused")),
            MockContextManager(return_value=mock_response_ok)
        ]

        engine, url, model = await self.node.probe_engine()
        
        self.assertEqual(engine, "VLLM")
        self.assertIn("127.0.0.1", url)
        print(f"[PASS] Successfully fell back to {engine} at {url}")

    @patch("nodes.loader.resolve_ip")
    @patch("aiohttp.ClientSession.get")
    async def test_kender_online_primary(self, mock_get, mock_resolve):
        """Verify that if KENDER is online, it is selected as primary."""
        mock_resolve.return_value = "192.168.1.26"
        
        mock_response_ok = AsyncMock()
        mock_response_ok.status = 200
        
        class MockContextManager:
            async def __aenter__(self): return mock_response_ok
            async def __aexit__(self, *args): pass

        mock_get.return_value = MockContextManager()

        engine, url, model = await self.node.probe_engine()
        
        self.assertEqual(engine, "OLLAMA")
        self.assertIn("192.168.1.26", url)
        print(f"[PASS] Successfully routed to Primary: {engine} at {url}")

if __name__ == "__main__":
    unittest.main()
