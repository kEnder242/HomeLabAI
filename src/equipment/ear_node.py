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
        
        # FIX: Sledgehammer - Recursively disable CUDA Graphs in all sub-objects
        # This solves the 'expected 6, got 5' error in NeMo 2.x
        def disable_cuda_graphs(obj, depth=0):
            if depth > 8: return 
            
            # 1. Force modes if methods exist
            if hasattr(obj, 'force_cuda_graphs_mode'):
                try:
                    obj.force_cuda_graphs_mode("no_graphs")
                except: pass
            
            if hasattr(obj, 'disable_cuda_graphs'):
                try:
                    obj.disable_cuda_graphs()
                except: pass

            # 2. Set flags
            for attr in ['cuda_graphs', 'allow_cuda_graphs', 'cuda_graphs_mode']:
                if hasattr(obj, attr):
                    try:
                        # Set to False or None depending on what it expects
                        if attr == 'cuda_graphs_mode':
                            setattr(obj, attr, None)
                        else:
                            setattr(obj, attr, False)
                    except: pass

            # 3. Recurse
            if hasattr(obj, '__dict__'):
                for attr_name in obj.__dict__:
                    try:
                        sub_obj = getattr(obj, attr_name)
                        disable_cuda_graphs(sub_obj, depth + 1)
                    except: pass
            
            # 4. Handle nn.Modules specifically
            if hasattr(obj, 'children'):
                for child in obj.children():
                    disable_cuda_graphs(child, depth + 1)

        disable_cuda_graphs(self.model)
        logging.info("👂 EarNode: CUDA Graphs definitively disabled (Heads-Up Fix).")
        
        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False
        self.wake_signal_sent = False

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
        
        try:
            # Reverting to the January logic which was stable
            outputs = self.model.forward(
                input_signal=audio_signal, 
                input_signal_length=torch.tensor([len(audio_signal[0])]).to("cuda")
            )
            
            # Extract encoded tensors (Standard RNNT indices)
            encoded = outputs[0]
            encoded_len = outputs[1]

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
        except Exception as e:
            logging.error(f"EarNode Inference Error: {e}")
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