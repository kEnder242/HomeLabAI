import asyncio
import websockets
import json
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
from threading import Lock
import time

# Configuration
SAMPLE_RATE = 16000
PORT = 8765
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"

# Rolling Window Config
BUFFER_DURATION = 1.5   # Total window size to transcribe
OVERLAP_DURATION = 0.5  # Amount of audio to keep for context
SILENCE_THRESHOLD = 100 # RMS threshold to skip silent chunks

BUFFER_SAMPLES = int(SAMPLE_RATE * BUFFER_DURATION) # 24000
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP_DURATION) # 8000
# We trigger inference when we have enough NEW data to fill the buffer
# But initially, we just grow to BUFFER_SAMPLES.

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Transcriber:
    def __init__(self):
        logging.info(f"Loading {MODEL_NAME}... (This may take a moment)")
        self.model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.model = self.model.to("cuda")
        logging.info("Model loaded on GPU.")
        self.last_text = ""
        
    @torch.no_grad()
    def transcribe(self, audio_data):
        # 1. Silence Check (Simple RMS)
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        if rms < SILENCE_THRESHOLD:
            return ""

        # 2. Prepare Tensor
        # Convert int16 to float32 normalized
        audio_signal = audio_data.astype(np.float32) / 32768.0
        audio_signal = torch.tensor(audio_signal).unsqueeze(0).to("cuda")
        
        try:
            # 3. Inference (RNNT)
            encoded, encoded_len = self.model.forward(
                input_signal=audio_signal, 
                input_signal_length=torch.tensor([len(audio_signal[0])]).to("cuda")
            )
            
            current_hypotheses = self.model.decoding.rnnt_decoder_predictions_tensor(
                encoded, encoded_len
            )
            
            if current_hypotheses and len(current_hypotheses) > 0:
                raw_text = current_hypotheses[0].text
                
                # 4. Basic Deduplication
                # If the new text completely contains the old text, return the *difference*?
                # Or just return the full text for now and let the client handle it?
                # For this phase, let's just log it and send it.
                # A simple heuristic: if it's the exact same string, ignore it.
                if raw_text == self.last_text:
                    return ""
                
                self.last_text = raw_text
                return raw_text
            return ""
            
        except Exception as e:
            logging.error(f"Inference error: {e}")
            return ""

# Global transcriber
transcriber = None

async def audio_handler(websocket):
    logging.info("Client connected!")
    # Initialize buffer with silence/zeros if needed, or empty
    audio_buffer = np.zeros(0, dtype=np.int16)
    
    try:
        async for message in websocket:
            # Receive raw audio
            chunk = np.frombuffer(message, dtype=np.int16)
            audio_buffer = np.concatenate((audio_buffer, chunk))
            
            # Check if we have enough data to fill the window
            if len(audio_buffer) >= BUFFER_SAMPLES:
                # Extract the window
                window = audio_buffer[:BUFFER_SAMPLES]
                
                # Transcribe
                start_time = time.time()
                text = transcriber.transcribe(window)
                duration = time.time() - start_time
                
                if text:
                    logging.info(f"Tx: '{text}' ({duration:.3f}s)")
                    await websocket.send(json.dumps({"text": text}))
                
                # Shift Buffer: Drop the oldest data, keep the overlap
                # New buffer = Overlap + (Remaining data in buffer)
                # Actually, correct rolling logic:
                # We processed [0 : BUFFER_SAMPLES]
                # We want to keep [BUFFER_SAMPLES - OVERLAP : ] as the start of next
                
                # Wait, simpler:
                # Keep the last OVERLAP_SAMPLES
                # Add any *excess* that wasn't processed yet (if we received a huge chunk)
                
                processed_count = BUFFER_SAMPLES - OVERLAP_SAMPLES
                audio_buffer = audio_buffer[processed_count:] 
                
    except websockets.exceptions.ConnectionClosed:
        logging.info("Client disconnected")
    except Exception as e:
        logging.error(f"Error in handler: {e}")

async def main():
    global transcriber
    transcriber = Transcriber() 
    
    logging.info(f"Starting WebSocket Server on 0.0.0.0:{PORT}")
    async with websockets.serve(audio_handler, "0.0.0.0", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
