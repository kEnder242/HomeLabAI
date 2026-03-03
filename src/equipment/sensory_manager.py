import logging
import os
import sys
import numpy as np
import random
import time
from infra.montana import reclaim_logger

class SensoryManager:
    """
    [FEAT-145] Sensory Manager: Modularized Audio & EarNode Logic.
    Encapsulates binary PCM processing and NeMo residency.
    Ready for [FEAT-147] Adaptive Residency (Dynamic load/unload).
    """
    def __init__(self, broadcast_callback):
        self.ear = None
        self.broadcast = broadcast_callback
        self.audio_buffer = np.zeros(0, dtype=np.int16)
        self.last_activity = time.time()
        reclaim_logger("SENSORY")
        
    async def load(self):
        """Lazy load real EarNode logic with CUDA Graph hardening."""
        if self.ear:
            return
            
        try:
            s_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if s_dir not in sys.path:
                sys.path.append(s_dir)
            
            # equipment is in the same directory as this file
            e_dir = os.path.dirname(os.path.abspath(__file__))
            if e_dir not in sys.path:
                sys.path.append(e_dir)
                
            from ear_node import EarNode
            self.ear = EarNode()
            logging.info("[SENSORY] EarNode initialized (NeMo).")
        except Exception as e:
            logging.error(f"[SENSORY] Failed to load EarNode: {e}")

    async def unload(self):
        """Unload NeMo model and reclaim VRAM. [FEAT-147]"""
        if not self.ear:
            return
            
        logging.info("[SENSORY] Unloading EarNode...")
        try:
            # Future: Call self.ear.stop() or delete if it supports it
            self.ear = None
            import torch
            torch.cuda.empty_cache()
            logging.info("[SENSORY] VRAM Reclaimed.")
        except Exception as e:
            logging.error(f"[SENSORY] Unload failed: {e}")

    def process_binary_chunk(self, data):
        """Processes raw PCM audio chunks from WebSocket."""
        if not self.ear:
            return None

        chunk = np.frombuffer(data, dtype=np.int16)
        self.audio_buffer = np.concatenate((self.audio_buffer, chunk))
        
        # Periodic signal detection log (5% chance if signal is high)
        if np.abs(chunk).max() > 500 and random.random() < 0.05:
            logging.info("[AUDIO] Signal detected.")
            
        if len(self.audio_buffer) >= 24000:
            text = self.ear.process_audio(self.audio_buffer[:24000])
            self.audio_buffer = self.audio_buffer[16000:] # Sliding window
            if text:
                self.last_activity = time.time()
                return text
        return None

    def check_turn_end(self):
        """Polls the EarNode for a finished transcription turn."""
        if self.ear:
            return self.ear.check_turn_end()
        return None
