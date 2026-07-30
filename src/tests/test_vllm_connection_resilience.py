import asyncio
import sys
import os
import unittest
from unittest.mock import patch, AsyncMock
import aiohttp
from yarl import URL

# Ensure src/ and parent dirs are in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.nodes.loader import BicameralNode

class TestVLLMConnectionResilience(unittest.TestCase):
    """
    [TEST-VLLM-RESILIENCE] Verifies that BicameralNode intercepts connection failures
    to vLLM (e.g. 127.0.0.1:8088 down/warming) in both ping_engine and generate_response,
    yielding clean character quips instead of raw python exception tracebacks.
    """

    def setUp(self):
        self.node = BicameralNode(name="pinky", system_prompt="You are Pinky.")

    def test_vllm_ping_failure_yields_friendly_quip(self):
        async def run_test():
            target_url = URL("http://127.0.0.1:8088/v1/models")
            req = aiohttp.ClientRequest("GET", target_url)
            conn_err = aiohttp.ClientConnectorError(
                connection_key=req.connection_key,
                os_error=OSError(111, "Connect call failed ('127.0.0.1', 8088)")
            )

            tokens = []
            # Mock aiohttp GET to throw ClientConnectorError when ping_engine probes port 8088
            with patch('aiohttp.ClientSession.get', side_effect=conn_err):
                async for token in self.node.generate_response(query="hi"):
                    tokens.append(token)

            full_output = "".join(tokens)
            print(f"[ping_engine failure] Captured output: {full_output}")

            # ASSERTIONS:
            # 1. Output must NOT contain raw Python tracebacks or "Connect call failed"
            self.assertNotIn("Connect call failed", full_output, "Raw traceback leaked into output during ping_engine!")
            self.assertNotIn("127.0.0.1:8088", full_output, "Raw IP/Port leaked into output during ping_engine!")
            
            # 2. Output MUST contain friendly character warming quip
            self.assertTrue(any(k in full_output for k in ["Narf!", "warming"]), f"Friendly warming quip expected! Got: {full_output}")

        asyncio.run(run_test())

    def test_vllm_stream_failure_yields_friendly_quip(self):
        async def run_test():
            # Pre-populate engine cache so ping_engine succeeds, but session.post fails
            self.node._engine_cache = {
                "url": "http://127.0.0.1:8088/v1/chat/completions",
                "model": "llama-3.2-3b-instruct-awq",
                "type": "VLLM",
                "available": ["llama-3.2-3b-instruct-awq"],
                "max_model_len": 16384
            }
            self.node._last_probe = 9999999999.0  # Fresh probe cache

            target_url = URL("http://127.0.0.1:8088/v1/chat/completions")
            req = aiohttp.ClientRequest("POST", target_url)
            conn_err = aiohttp.ClientConnectorError(
                connection_key=req.connection_key,
                os_error=OSError(111, "Connect call failed ('127.0.0.1', 8088)")
            )

            tokens = []
            with patch('aiohttp.ClientSession.post', side_effect=conn_err):
                async for token in self.node.generate_response(query="hi"):
                    tokens.append(token)

            full_output = "".join(tokens)
            print(f"[stream failure] Captured output: {full_output}")

            # ASSERTIONS:
            self.assertNotIn("Connect call failed", full_output, "Raw traceback leaked into output during streaming!")
            self.assertTrue(any(k in full_output for k in ["Narf!", "warming"]), f"Friendly warming quip expected! Got: {full_output}")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
