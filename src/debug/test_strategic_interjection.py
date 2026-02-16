import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from acme_lab import AcmeLab

class TestStrategicInterjection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.lab = AcmeLab(mode="DEBUG_SMOKE")
        # Mock residents
        self.mock_pinky = AsyncMock()
        self.mock_brain = AsyncMock()
        self.lab.residents = {
            "pinky": self.mock_pinky,
            "brain": self.mock_brain
        }
        self.lab.brain_online = True

    @patch("acme_lab.AcmeLab.broadcast")
    async def test_strategic_keyword_triggers_brain(self, mock_broadcast):
        """Verify that a strategic keyword (regression) triggers both Pinky and Brain."""
        query = "We have a major regression in the silicon drivers."
        
        # Pinky response
        mock_res_pinky = MagicMock()
        mock_res_pinky.content = [MagicMock(text=json.dumps({"reply_to_user": "Narf! Silicon!"}))]
        self.mock_pinky.call_tool.return_value = mock_res_pinky
        
        # Brain response
        mock_res_brain = MagicMock()
        mock_res_brain.content = [MagicMock(text=json.dumps({"reply_to_user": "Technical analysis of the regression..."}))]
        self.mock_brain.call_tool.return_value = mock_res_brain

        await self.lab.process_query(query, None)
        
        # Verify both were called
        self.mock_pinky.call_tool.assert_called_with(name="facilitate", arguments={"query": query, "context": ""})
        self.mock_brain.call_tool.assert_called()
        print("[PASS] Both Pinky and Brain were engaged by strategic keyword.")

    @patch("acme_lab.AcmeLab.broadcast")
    async def test_direct_address_triggers_brain(self, mock_broadcast):
        """Verify that addressing 'Brain' triggers the interjection message and Brain response."""
        query = "Brain, tell me about the architecture."
        
        mock_res_pinky = MagicMock()
        mock_res_pinky.content = [MagicMock(text=json.dumps({"reply_to_user": "Pinky response"}))]
        self.mock_pinky.call_tool.return_value = mock_res_pinky
        
        mock_res_brain = MagicMock()
        mock_res_brain.content = [MagicMock(text=json.dumps({"reply_to_user": "Brain analysis"}))]
        self.mock_brain.call_tool.return_value = mock_res_brain

        await self.lab.process_query(query, None)
        
        # Check if Pinky interjected the "Narf! I'll wake up the Left Hemisphere!" message
        found_handover = any("wake up the Left Hemisphere" in str(c) for c in mock_broadcast.call_args_list)
        self.assertTrue(found_handover)
        self.mock_brain.call_tool.assert_called()
        print("[PASS] Direct addressing triggered handover and Brain engagement.")

if __name__ == "__main__":
    import json
    unittest.main()
