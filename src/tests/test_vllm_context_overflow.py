import unittest
import asyncio
import os
import sys

# Ensure HomeLabAI/src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nodes.loader import BicameralNode

class TestVllmContextOverflow(unittest.TestCase):
    def setUp(self):
        self.loader = BicameralNode("test_node", system_prompt="Test System Prompt")
        # Mock engine cache with 16384 context
        self.loader._engine_cache = {
            "url": "http://127.0.0.1:8088/v1/chat/completions",
            "model": "unified-base",
            "type": "VLLM",
            "available": ["unified-base"],
            "max_model_len": 16384
        }

    def test_oversized_prompt_truncation(self):
        async def run_test():
            # Create a 16000 token prompt (~60,000 chars)
            oversized_query = "word " * 16000
            tokens = []
            async for token in self.loader.generate_response(oversized_query, max_tokens=150):
                tokens.append(token)
            return "".join(tokens)

        loop = asyncio.get_event_loop()
        output = loop.run_until_complete(run_test())
        # Verify output is NOT a 400 error box
        self.assertNotIn("Error: vLLM returned 400", output)

if __name__ == "__main__":
    unittest.main()
