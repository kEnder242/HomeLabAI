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
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
SAMPLE_RATE = 16000
PORT = 8765
MODEL_NAME = "nvidia/nemotron-speech-streaming-en-0.6b"
BUILD_VERSION = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Pinky (Local) Config
PINKY_URL = "http://localhost:11434/api/generate"
PINKY_MODEL = "llama3.1:8b"
SILENCE_TIMEOUT = 1.2

# System Prompts
PINKY_SYSTEM_PROMPT = (
    "You are Pinky, a genetically enhanced mouse residing in a Linux server. "
    "You are cheerful, enthusiastic, and helpful, but you have a limited attention span. "
    "You speak with interjections like 'Narf!', 'Poit!', 'Egad!', and 'Zort!'. "
    "Your goal is to handle simple greetings, small talk, and basic questions personally. "
    "If the user asks for complex coding, detailed reasoning, or math, "
    "acknowledge it and say you'll ask the Brain."
)

# RAG Config
DB_PATH = os.path.expanduser("~/VoiceGateway/chroma_db")
COLLECTION_NAME = "personal_knowledge"

# Audio Buffering
BUFFER_DURATION = 1.5
OVERLAP_DURATION = 0.5
SILENCE_THRESHOLD = 100
BUFFER_SAMPLES = int(SAMPLE_RATE * BUFFER_DURATION)
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP_DURATION)

# Logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/conversation.log"),
        logging.StreamHandler()
    ]
)

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

class Transcriber:
    def __init__(self):
        logging.info(f"[{BUILD_VERSION}] Loading {MODEL_NAME}...")
        self.model = nemo_asr.models.ASRModel.from_pretrained(MODEL_NAME)
        self.model.eval()
        self.model = self.model.to("cuda")
        
        # RAG Init
        self.chroma_client = chromadb.PersistentClient(path=DB_PATH)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.collection = self.chroma_client.get_collection(
            name=COLLECTION_NAME, embedding_function=ef
        )
        
        self.full_transcript = ""
        self.last_speech_time = time.time()
        self.turn_pending = False

    @torch.no_grad()
    def transcribe(self, audio_data):
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        if rms < SILENCE_THRESHOLD: return None

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
            logging.error(f"Inference error: {e}")
        return None

class PinkyMCPHost:
    def __init__(self, transcriber):
        self.transcriber = transcriber
        self.brain_session = None

    async def connect_brain(self):
        """Connect to the Brain MCP Server via stdio."""
        python_path = "/home/jallred/VoiceGateway/.venv/bin/python"
        server_params = StdioServerParameters(
            command=python_path,
            args=["src/brain_mcp_server.py"],
        )
        logging.info("🧠 Connecting to Brain MCP Server via Stdio...")
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=15.0)
                    self.brain_session = session
                    logging.info("✅ Brain MCP Session Initialized.")
                    while True:
                        await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"❌ Brain MCP Failed: {e}")

    async def handle_query(self, query, websocket):
        logging.info(f"[USER] {query}")
        
        # RAG Search
        context = ""
        try:
            results = self.transcriber.collection.query(query_texts=[query], n_results=2)
            if results and results['documents']:
                docs = results['documents'][0]
                context = "\n".join(docs)
        except Exception as e:
            logging.error(f"RAG Error: {e}")

        # Decide: Pinky vs Brain
        needs_brain = any(word in query.lower() for word in ["code", "script", "plan", "complex", "math", "why"])
        
        if needs_brain:
            logging.info("🧠 Escalating to THE BRAIN via MCP Tool Call.")
            await websocket.send(json.dumps({
                "brain": "Narf! That's a brain-teaser! Let me ask the Brain! *Poit!*",
                "brain_source": "Pinky (Escalation)"
            }))
            
            # Call Brain MCP Tool
            if self.brain_session:
                await asyncio.sleep(2.0) # Safety buffer for session readiness
                try:
                    result = await asyncio.wait_for(
                        self.brain_session.call_tool("deep_think", arguments={"query": query, "context": context}),
                        timeout=60.0
                    )
                    response_text = result.content[0].text
                    logging.info(f"[BRAIN] {response_text}")
                    await websocket.send(json.dumps({
                        "brain": response_text,
                        "brain_source": "The Brain (MCP)"
                    }))
                except Exception as e:
                    logging.error(f"Brain Tool Call Failed: {e}")
                    await websocket.send(json.dumps({"brain": f"The Brain is being difficult: {e}", "brain_source": "Pinky"}))
            else:
                await websocket.send(json.dumps({"brain": "The Brain is missing! Zort!", "brain_source": "Pinky"}))
        else:
            # Pinky handles it
            logging.info("🐹 Pinky is handling this locally.")
            prompt = f"{PINKY_SYSTEM_PROMPT}\nContext: {context}\nUser: {query}"
            response = await self.generate_pinky(prompt)
            logging.info(f"[PINKY] {response}")
            await websocket.send(json.dumps({
                "brain": response,
                "brain_source": "Pinky (Local)"
            }))

    async def generate_pinky(self, prompt):
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"model": PINKY_MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": 200}}
                async with session.post(PINKY_URL, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "Narf!")
        except Exception as e:
            return f"Egad! Pinky failed: {e}"
        return "Narf!"

async def audio_handler(websocket, host):
    logging.info("Client connected!")
    audio_buffer = np.zeros(0, dtype=np.int16)
    
    try:
        async for message in websocket:
            # Handle Debug Text Injection
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    if "debug_text" in data:
                        query = data["debug_text"]
                        logging.info(f"🐛 Debug Text Injected: '{query}'")
                        asyncio.create_task(host.handle_query(query, websocket))
                except Exception as e:
                    logging.error(f"Debug text error: {e}")
                continue

            chunk = np.frombuffer(message, dtype=np.int16)
            audio_buffer = np.concatenate((audio_buffer, chunk))
            
            if len(audio_buffer) >= BUFFER_SAMPLES:
                window = audio_buffer[:BUFFER_SAMPLES]
                text = host.transcriber.transcribe(window)
                if text:
                    logging.info(f"Tx: '{text}'")
                    await websocket.send(json.dumps({"text": text}))
                audio_buffer = audio_buffer[BUFFER_SAMPLES - OVERLAP_SAMPLES:]
            
            # Check turn end
            if host.transcriber.turn_pending and (time.time() - host.transcriber.last_speech_time > SILENCE_TIMEOUT):
                host.transcriber.turn_pending = False
                query = host.transcriber.full_transcript.strip()
                host.transcriber.full_transcript = ""
                if query:
                    asyncio.create_task(host.handle_query(query, websocket))
                
    except Exception as e:
        logging.info(f"Handler exiting: {e}")

async def main():
    transcriber = Transcriber()
    host = PinkyMCPHost(transcriber)
    
    python_path = "/home/jallred/VoiceGateway/.venv/bin/python"
    server_params = StdioServerParameters(
        command=python_path,
        args=["src/brain_mcp_server.py"],
    )
    
    logging.info(f"Starting Pinky MCP Host on 0.0.0.0:{PORT}")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            logging.info("🧠 Connecting to Brain MCP Server via Stdio...")
            await session.initialize()
            host.brain_session = session
            logging.info("✅ Brain MCP Session Initialized.")
            
            async with websockets.serve(lambda ws: audio_handler(ws, host), "0.0.0.0", PORT):
                await asyncio.Future() # run forever

if __name__ == "__main__":
    asyncio.run(main())
