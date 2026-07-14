from typing import Dict

class CognitiveHub:
    def __init__(self):
        self.context = {}

    def process_signal(self, signal: str) -> None:
        """Process a signal and update context"""
        if signal.startswith('/topic reset'):
            self.context.clear()

    def get_context(self) -> Dict:
        """Return current context"""
        return self.context