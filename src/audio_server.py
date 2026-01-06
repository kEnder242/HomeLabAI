import asyncio
import websockets
import json
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
import time
import datetime
import aiohttp

# Configuration
SAMPLE_RATE = 16000
PORT = 8765
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
BUILD_VERSION = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# "Thinking" Config
OLLAMA_URL = "http://192.168.1.26:11434/api/generate"
# OLLAMA_MODEL = "llama3:70b"  # Use your preferred model
OLLAMA_MODEL = "llama3:latest" # Valid model on host
SILENCE_TIMEOUT = 1.2 # Seconds of silence to trigger a "Turn"

# Rolling Window Config
BUFFER_DURATION = 1.5   
OVERLAP_DURATION = 0.5  
SILENCE_THRESHOLD = 100 

BUFFER_SAMPLES = int(SAMPLE_RATE * BUFFER_DURATION) 
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP_DURATION)

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_new_text(old_text, new_window_text):
    if not old_text:
        return new_window_text
    old_words = old_text.strip().split()
    new_words = new_window_text.strip().split()
    if not new_words:
        return ""
    max_overlap = min(len(old_words), len(new_words), 5)
    for i in range(max_overlap, 0, -1):
        if old_words[-i:] == new_words[:i]:
            return " ".join(new_words[i:])
    return new_window_text

class Transcriber:
    def __init__(self):
        logging.info(f"[{BUILD_VERSION}] Loading {MODEL_NAME}...")
        self.model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.model = self.model.to("cuda")
        logging.info("Model loaded on GPU.")
        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False
        
    @torch.no_grad()
    def transcribe(self, audio_data):
        # 1. Silence Check
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        if rms < SILENCE_THRESHOLD:
            return None # Explicit None for silence

        # 2. Prepare Tensor
        audio_signal = audio_data.astype(np.float32) / 32768.0
        audio_signal = torch.tensor(audio_signal).unsqueeze(0).to("cuda")
        
        try:
            # 3. Inference
            encoded, encoded_len = self.model.forward(
                input_signal=audio_signal, 
                input_signal_length=torch.tensor([len(audio_signal[0])]).to("cuda")
            )
            
            current_hypotheses = self.model.decoding.rnnt_decoder_predictions_tensor(
                encoded, encoded_len
            )
            
            if current_hypotheses and len(current_hypotheses) > 0:
                raw_text = current_hypotheses[0].text
                if not raw_text:
                    return None
                
                # 4. Alignment / Deduplication
                incremental_text = get_new_text(self.full_transcript, raw_text)
                
                if incremental_text:
                    self.full_transcript += " " + incremental_text
                    self.last_speech_time = time.time() # Reset silence timer
                    self.turn_pending = True
                    return incremental_text.strip()
            return None
            
        except Exception as e:
            logging.error(f"Inference error: {e}")
            return None

    async def check_turn_end(self):
        """Checks if silence duration exceeds timeout and triggers Ollama."""
        if self.turn_pending and (time.time() - self.last_speech_time > SILENCE_TIMEOUT):
            # Turn End Detected!
            self.turn_pending = False
            user_query = self.full_transcript.strip()
            self.full_transcript = "" # Reset for next turn
            
            if user_query:
                logging.info(f"🤔 Thinking about: '{user_query}'")
                await self.ask_ollama(user_query)
                return True
        return False

    async def ask_ollama(self, query):
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": query,
                    "stream": False
                }
                async with session.post(OLLAMA_URL, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response_text = data.get("response", "")
                        logging.info(f"💡 Brain: {response_text[:200]}...") # Log first 200 chars
                    else:
                        logging.error(f"Ollama Error: {resp.status}")
        except Exception as e:
            logging.error(f"Brain Connection Failed: {e}")

# Global state
transcriber = None
shutdown_event = asyncio.Event()

async def audio_handler(websocket):
    logging.info("Client connected!")
    audio_buffer = np.zeros(0, dtype=np.int16)
    
    try:
        async for message in websocket:
            chunk = np.frombuffer(message, dtype=np.int16)
            audio_buffer = np.concatenate((audio_buffer, chunk))
            
            # Transcription Loop
            if len(audio_buffer) >= BUFFER_SAMPLES:
                window = audio_buffer[:BUFFER_SAMPLES]
                
                start_time = time.time()
                text = transcriber.transcribe(window)
                duration = time.time() - start_time
                
                if text:
                    logging.info(f"Tx: '{text}' ({duration:.3f}s)")
                    await websocket.send(json.dumps({"text": text}))
                
                # Shift Buffer
                processed_count = BUFFER_SAMPLES - OVERLAP_SAMPLES
                audio_buffer = audio_buffer[processed_count:] 
                
            # Check for Silence / Turn End (Every chunk)
            await transcriber.check_turn_end()
                
    except Exception as e:
        logging.info(f"Handler exiting: {e}")
    finally:
        logging.info("Client disconnected. Shutting down server...")
        shutdown_event.set()

async def main():
    global transcriber
    transcriber = Transcriber() 
    
    logging.info(f"Starting WebSocket Server on 0.0.0.0:{PORT}")
    try:
        async with websockets.serve(audio_handler, "0.0.0.0", PORT):
            await shutdown_event.wait()
    except Exception as e:
        logging.error(f"Server error: {e}")
    
    logging.info("Server stopped.")

if __name__ == "__main__":
    asyncio.run(main())
