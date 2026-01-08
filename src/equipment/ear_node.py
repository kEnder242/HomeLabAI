import asyncio
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
import time
import datetime

# Configuration
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
SILENCE_THRESHOLD = 100

def get_new_text(old_text, new_window_text):
    if not old_text: return new_window_text
    old_words = old_text.strip().split()
    new_words = new_window_text.strip().split()
    if not new_words: return ""
    max_overlap = min(len(old_words), len(new_words), 5)
    for i in range(max_overlap, 0, -1):
        if old_words[-i:] == new_words[:i]:
            return " ".join(new_words[i:])
    return new_window_text

class EarNode:
    def __init__(self, callback):
        self.callback = callback # Function to call with new text
        logging.info(f"👂 EarNode: Loading {MODEL_NAME}...")
        self.model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.model = self.model.to("cuda")
        
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

        # Wake Signal (First speech detected)
        if not self.wake_signal_sent:
            self.wake_signal_sent = True
            # In the Acme Lab, the Lab itself handles the 'Wake Brain' logic via callback if needed, 
            # or we just treat this as 'Sound Detected'.
            pass

        audio_signal = audio_data.astype(np.float32) / 32768.0
        audio_signal = torch.tensor(audio_signal).unsqueeze(0).to("cuda")
        
        try:
            encoded, encoded_len = self.model.forward(
                input_signal=audio_signal, 
                input_signal_length=torch.tensor([len(audio_signal[0])]).to("cuda")
            )
            current_hypotheses = self.model.decoding.rnnt_decoder_predictions_tensor(encoded, encoded_len)
            if current_hypotheses and len(current_hypotheses) > 0:
                raw_text = current_hypotheses[0].text
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

    def check_turn_end(self, silence_timeout=0.8):
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
