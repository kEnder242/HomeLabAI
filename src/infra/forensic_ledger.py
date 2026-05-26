import os
import json
import datetime
import logging
from typing import Dict, Any

class ForensicLedger:
    """
    [BKM-032] The Wordy Logger.
    Captures 100% of the inter-node thought traces into a persistent ledger
    for deferred semantic evaluation by the AI.
    """
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # [Task 6.1] Initialize the evaluation batch file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ledger_path = os.path.join(self.log_dir, f"evaluation_batch_{timestamp}.log")
        
        logging.info(f"[LEDGER] Initialized Wordy Logger at: {self.ledger_path}")

    def record_thought(self, node: str, content: str, role: str = "THOUGHT"):
        """Appends a thought block to the persistent ledger."""
        try:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "node": node,
                "role": role,
                "content": content
            }
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.error(f"[LEDGER] Failed to record thought: {e}")

    def record_interaction(self, query: str, response: str, metadata: Dict[str, Any] = None):
        """Records a full interaction turn with metadata."""
        try:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "INTERACTION",
                "query": query,
                "response": response,
                "metadata": metadata or {}
            }
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.error(f"[LEDGER] Failed to record interaction: {e}")

# Global instance for easy access
ledger = ForensicLedger()
