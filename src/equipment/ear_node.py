import asyncio
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
import time
import datetime
from dedup_utils import get_new_text

# Configuration
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
SILENCE_THRESHOLD = 80

class EarNode:
    def __init__(self, callback):
        self.callback = callback # Function to call with new text
        logging.info(f"👂 EarNode: Loading {MODEL_NAME}...")
        self.model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.model = self.model.to("cuda")
        
        self.cuda_graph_failed = False
        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False
        self.wake_signal_sent = False

    def _sledgehammer_disable_graphs(self):
        """Recursively disables CUDA Graphs across the entire model tree."""
        logging.warning("⚠️ EarNode: Triggering Sledgehammer recovery (disabling CUDA Graphs)...")
        def disable_recursive(obj, depth=0):
            if depth > 8: return 
            if hasattr(obj, 'force_cuda_graphs_mode'):
                try: obj.force_cuda_graphs_mode("no_graphs")
                except: pass
            if hasattr(obj, 'disable_cuda_graphs'):
                try: obj.disable_cuda_graphs()
                except: pass
            for attr in ['cuda_graphs', 'allow_cuda_graphs', 'cuda_graphs_mode']:
                if hasattr(obj, attr):
                    try: setattr(obj, attr, None if attr == 'cuda_graphs_mode' else False)
                    except: pass
            if hasattr(obj, '__dict__'):
                for attr_name in obj.__dict__:
                    try: disable_recursive(getattr(obj, attr_name), depth + 1)
                    except: pass
            if hasattr(obj, 'children'):
                for child in obj.children():
                    disable_recursive(child, depth + 1)
        
        disable_recursive(self.model)
        self.cuda_graph_failed = True
        logging.info("👂 EarNode: Self-healed into Eager Mode.")

    @torch.no_grad()
    def process_audio(self, audio_data):
        """
        Takes raw audio buffer (numpy int16), performs inference.
        Returns incremental text if any.
        """
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        if rms < SILENCE_THRESHOLD: return None

        audio_signal = audio_data.astype(np.float32) / 32768.0
        audio_signal = torch.tensor(audio_signal).unsqueeze(0).to("cuda")
        
        # We try twice: once optimistically, once after healing if needed
        for attempt in range(2):
            try:
                outputs = self.model.forward(
                    input_signal=audio_signal, 
                    input_signal_length=torch.tensor([len(audio_signal[0])]).to("cuda")
                )
                
                # Robust extraction: NeMo RNNT forward usually returns (encoded, encoded_len, ...)
                if isinstance(outputs, (list, tuple)) and len(outputs) >= 2:
                    encoded = outputs[0]
                    encoded_len = outputs[1]
                else:
                    encoded = outputs
                    encoded_len = torch.tensor([encoded.shape[1]]).to("cuda")

                current_hypotheses = self.model.decoding.rnnt_decoder_predictions_tensor(encoded, encoded_len)
                
                if current_hypotheses and len(current_hypotheses) > 0:
                    raw_text = current_hypotheses[0].text
                    if raw_text:
                        logging.info(f"👂 EarNode: Hypothesis found: {raw_text}")
                    if not raw_text: return None
                    
                    incremental_text = get_new_text(self.full_transcript, raw_text)
                    if incremental_text:
                        self.full_transcript += " " + incremental_text
                        self.last_speech_time = time.time()
                        self.turn_pending = True
                        return incremental_text.strip()
                return None # No text found but no error

            except Exception as e:
                # Catch the specific unpacking error or any other graph-related crash
                if ("unpack" in str(e) or "cu_call" in str(e)) and not self.cuda_graph_failed:
                    self._sledgehammer_disable_graphs()
                    continue 
                else:
                    logging.error(f"EarNode Inference Error: {e}")
                    return None
        return None

    def check_turn_end(self, silence_timeout=1.2):
        """
        Checks if the user has stopped speaking.
        Returns the full query if turn ended, else None.
        """
        if self.turn_pending and (time.time() - self.last_speech_time > silence_timeout):
            self.turn_pending = False
            self.wake_signal_sent = False # Reset for next turn
            query = self.full_transcript.strip()
            self.full_transcript = ""
            return query
        return None
