import asyncio
import json
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Set up paths
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "field_notes/data/interaction_history.json")

from acme_lab import AcmeLab

class TestHubPersistence(unittest.IsolatedAsyncioTestCase):
    """
    [Task 3.3] Verification for Selective Persistence (Hibernation Rule).
    """
    
    def setUp(self):
        # Ensure clean state
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            
    def tearDown(self):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)

    @patch('acme_lab.SensoryManager', MagicMock())
    @patch('acme_lab.CognitiveHub', MagicMock())
    @patch('acme_lab.reclaim_logger', MagicMock())
    @patch('infra.atomic_io.atomic_write_json')
    @patch('os.open', MagicMock(return_value=999))
    @patch('os.fsync', MagicMock())
    @patch('os.write', MagicMock())
    @patch('os.close', MagicMock())
    async def test_history_persistence(self, mock_write):
        print("\n--- [TASK 3.3] VERIFICATION: HUB PERSISTENCE ---")
        
        # 1. Initialize and add history
        lab = AcmeLab()
        test_msg = {"type": "chat", "brain": "Persisted message", "msg_id": "123"}
        lab.message_history.append(test_msg)
        
        # 2. Save manually
        lab._save_history()
        print("[STEP 1] History saved.")
        mock_write.assert_called()
        
        # 3. Mock loading from a file (testing _load_history)
        with patch('builtins.open', MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=json.dumps([test_msg]))))))), \
             patch('os.path.exists', return_value=True):
            lab2 = AcmeLab()
            print(f"[STEP 2] Loaded history: {lab2.message_history}")
            self.assertEqual(len(lab2.message_history), 1)
            self.assertEqual(lab2.message_history[0]["brain"], "Persisted message")

    @patch('acme_lab.SensoryManager', MagicMock())
    @patch('acme_lab.CognitiveHub', MagicMock())
    @patch('acme_lab.reclaim_logger', MagicMock())
    @patch('infra.atomic_io.atomic_write_json')
    @patch('os.open', MagicMock(return_value=999))
    @patch('os.fsync', MagicMock())
    @patch('os.write', MagicMock())
    @patch('os.close', MagicMock())
    async def test_hibernation_rule(self, mock_write):
        print("\n--- [STEP 3] HIBERNATION RULE (H2) ---")
        lab = AcmeLab()
        lab.residents["archive"] = AsyncMock()
        lab.residents["archive"].call_tool = AsyncMock(return_value=MagicMock())
        
        # Add history
        lab.message_history.append({"type": "chat", "brain": "Stay alive", "msg_id": "456"})
        
        # Trigger H2 Hibernate
        with patch('aiohttp.ClientSession.post', new_callable=MagicMock) as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await lab._hibernate(level=2)
            
        print("[STEP 3] H2 triggered. Checking persistence...")
        mock_write.assert_called()
        
        # Verify archive clipboard cleared
        lab.residents["archive"].call_tool.assert_called_with("clear_clipboard", {})
        print("✅ Task 3.3 Verification: Persistence and Hibernation Rule verified.")

if __name__ == "__main__":
    unittest.main()
