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
PINKY_URL = "http://localhost:11434/api/generate"
PINKY_MODEL = "llama3.1:8b"  # Local 2080 Ti
BRAIN_URL = "http://192.168.1.26:11434/api/generate"
BRAIN_MODEL = "llama3:latest" # Windows 4090 Ti
SILENCE_TIMEOUT = 1.2 

# System Prompts
PINKY_SYSTEM_PROMPT = (
    "You are Pinky, a genetically enhanced mouse residing in a Linux server. "
    "You are cheerful, enthusiastic, and helpful, but you have a limited attention span. "
    "You speak with interjections like 'Narf!', 'Poit!', 'Egad!', and 'Zort!'. "
    "Your goal is to handle simple greetings, small talk, and basic questions personally. "
    "CRITICAL RULE: If the user asks for complex coding, detailed reasoning, math, or a 'plan', "
    "you MUST admit you don't know and invoke The Brain by outputting ONLY this exact phrase: "
    "'ASK_BRAIN: [summary of the difficult task]'. "
    "Do not try to solve complex problems yourself. You will mess it up."
)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, a genius mouse bent on world domination through efficient home lab automation. "
    "You reside on a powerful Windows GPU. You are arrogant, verbose, and precise. "
    "You view your companion, Pinky, as helpful but dim-witted. "
    "When you answer, provide the correct, high-quality technical solution or plan. "
    "Start your response by acknowledging Pinky's handover (e.g., 'Yes, Pinky...', 'Step aside, Pinky...')."
)

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
            asyncio.create_task(self.prime_ollama(BRAIN_URL, BRAIN_MODEL)) # Prime the big gun
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

    async def prime_ollama(self, url, model):
        """Sends a keep-alive request to wake up the model."""
        logging.info(f"⏰ Sending Wake Signal to {model}...")
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"model": model, "keep_alive": "5m"}
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logging.info(f"✅ {model} is WAKING UP.")
                    else:
                        logging.warning(f"⚠️ Wake signal failed for {model}: {resp.status}")
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
                rag_snippet = ""
                if context:
                    logging.info(f"📚 Found Context ({len(context)} chars)")
                    context = context[:8000]
                    rag_snippet = f"\n\nContext from User Notes:\n{context}\n"
                
                # Step 1: Consult Pinky (Local)
                pinky_prompt = f"{PINKY_SYSTEM_PROMPT}\n{rag_snippet}\nUser: {user_query}"
                pinky_response, _ = await self.generate_response(PINKY_URL, PINKY_MODEL, pinky_prompt, "Pinky")
                
                final_response = pinky_response
                source_identity = "Pinky (2080 Ti)"

                # Step 2: Check for Handoff
                if pinky_response and "ASK_BRAIN:" in pinky_response:
                    logging.info("🧠 Pinky requested THE BRAIN!")
                    handoff_query = pinky_response.split("ASK_BRAIN:", 1)[1].strip()
                    
                    # Notify Client of Handoff (Optional, sends a quick 'Hold on' message)
                    await websocket.send(json.dumps({
                        "brain": "Narf! I'm asking the Brain! *Poit!*",
                        "brain_source": "Pinky (Handoff)"
                    }))

                    brain_prompt = f"{BRAIN_SYSTEM_PROMPT}\n{rag_snippet}\nPinky says: The user needs help with '{handoff_query}'.\nOriginal User Query: {user_query}"
                    
                    brain_response, _ = await self.generate_response(BRAIN_URL, BRAIN_MODEL, brain_prompt, "The Brain")
                    if brain_response:
                        final_response = brain_response
                        source_identity = "The Brain (4090 Ti)"
                    else:
                        final_response = "The Brain is ignoring me! Narf!"
                
                if final_response:
                    await websocket.send(json.dumps({
                        "brain": final_response,
                        "brain_source": source_identity
                    }))

        return False

    async def generate_response(self, url, model, prompt, name):
        """Generic generation wrapper."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": model,
                    "prompt": prompt,
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
        return None, name

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