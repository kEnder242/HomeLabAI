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
import os
import chromadb
from chromadb.utils import embedding_functions

# Configuration
SAMPLE_RATE = 16000
PORT = 8765
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
BUILD_VERSION = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# "Thinking" Config
OLLAMA_URL = "http://192.168.1.26:11434/api/generate"
OLLAMA_MODEL = "llama3:latest" 
SILENCE_TIMEOUT = 1.2 

# RAG Config
DB_PATH = os.path.expanduser("~/VoiceGateway/chroma_db")
COLLECTION_NAME = "personal_knowledge"

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
        
        # RAG Init
        logging.info(f"Connecting to Knowledge Base at {DB_PATH}...")
        self.chroma_client = chromadb.PersistentClient(path=DB_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.collection = self.chroma_client.get_collection(
            name=COLLECTION_NAME, embedding_function=ef
        )
        logging.info("Knowledge Base connected.")

        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False
        self.wake_signal_sent = False
        
    @torch.no_grad()
    def transcribe(self, audio_data):
        # 1. Silence Check
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        if rms < SILENCE_THRESHOLD:
            return None 

        # 2. Wake Signal (Fire Once)
        if not self.wake_signal_sent:
            asyncio.create_task(self.prime_ollama())
            self.wake_signal_sent = True

        # 3. Prepare Tensor
        audio_signal = audio_data.astype(np.float32) / 32768.0
        audio_signal = torch.tensor(audio_signal).unsqueeze(0).to("cuda")
        
        try:
            # 4. Inference
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
                
                incremental_text = get_new_text(self.full_transcript, raw_text)
                
                if incremental_text:
                    self.full_transcript += " " + incremental_text
                    self.last_speech_time = time.time() 
                    self.turn_pending = True
                    return incremental_text.strip()
            return None
            
        except Exception as e:
            logging.error(f"Inference error: {e}")
            return None

    async def prime_ollama(self):
        """Sends a keep-alive request to wake up the model."""
        logging.info("⏰ Sending Wake Signal to Ollama...")
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"model": OLLAMA_MODEL, "keep_alive": "5m"}
                async with session.post(OLLAMA_URL, json=payload) as resp:
                    if resp.status == 200:
                        logging.info("✅ Ollama is WAKING UP.")
                    else:
                        logging.warning(f"⚠️ Wake signal failed: {resp.status}")
        except Exception as e:
            logging.error(f"⚠️ Wake signal error: {e}")

    async def search_knowledge_base(self, query):
        """Queries ChromaDB for context."""
        try:
            results = self.collection.query(query_texts=[query], n_results=2)
            if results and results['documents']:
                # Flatten list of list
                docs = results['documents'][0]
                sources = results['metadatas'][0]
                context = "\n".join([f"--- Source: {m.get('source', '?')} ---\n{d}" for d, m in zip(docs, sources)])
                return context
        except Exception as e:
            logging.error(f"RAG Error: {e}")
        return ""

    async def check_turn_end(self, websocket):
        if self.turn_pending and (time.time() - self.last_speech_time > SILENCE_TIMEOUT):
            # Turn End
            self.turn_pending = False
            self.wake_signal_sent = False 
            user_query = self.full_transcript.strip()
            self.full_transcript = "" 
            
            if user_query:
                logging.info(f"🤔 Thinking about: '{user_query}'")
                
                # RAG Step
                context = await self.search_knowledge_base(user_query)
                if context:
                    logging.info(f"📚 Found Context ({len(context)} chars)")
                    context = context[:8000] 
                    # Improved System Prompt to reduce hallucinations
                    final_prompt = (
                        f"System: You are a helpful assistant. The following context is retrieved from the user's notes. "
                        f"If the context is NOT relevant to the user's question, IGNORE IT and answer normally.\n\n"
                        f"Context:\n{context}\n\n"
                        f"User: {user_query}"
                    )
                else:
                    final_prompt = user_query
                
                response_text, brain_source = await self.ask_ollama(final_prompt)
                
                if response_text:
                    # Send back to client with source info
                    await websocket.send(json.dumps({
                        "brain": response_text,
                        "brain_source": brain_source
                    }))

        return False

    async def ask_ollama(self, query):
        """Tries Windows Brain, falls back to Linux Brain. Returns (text, source_name)."""
        urls = [
            (OLLAMA_URL, OLLAMA_MODEL, "Windows 4080 Ti"),
            ("http://localhost:11434/api/generate", "llama3.1:8b", "Linux 2080 Ti (Fallback)")
        ]

        for url, model, name in urls:
            try:
                # logging.info(f"Trying {name}...") 
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "model": model,
                        "prompt": query,
                        "stream": False
                    }
                    timeout = aiohttp.ClientTimeout(total=60, connect=2)
                    
                    async with session.post(url, json=payload, timeout=timeout) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            response_text = data.get("response", "")
                            logging.info(f"💡 {name}: {response_text[:100]}...") 
                            return response_text, name
                        else:
                            logging.warning(f"⚠️ {name} Error: {resp.status}")
            except Exception as e:
                logging.warning(f"⚠️ {name} Failed: {e}")
        
        logging.error("❌ ALL BRAINS FAILED.")
        return "I'm sorry, my brain is offline.", "Offline"

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
            
            if len(audio_buffer) >= BUFFER_SAMPLES:
                window = audio_buffer[:BUFFER_SAMPLES]
                start_time = time.time()
                text = transcriber.transcribe(window)
                duration = time.time() - start_time
                if text:
                    logging.info(f"Tx: '{text}' ({duration:.3f}s)")
                    await websocket.send(json.dumps({"text": text}))
                processed_count = BUFFER_SAMPLES - OVERLAP_SAMPLES
                audio_buffer = audio_buffer[processed_count:] 
                
            await transcriber.check_turn_end(websocket)
                
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