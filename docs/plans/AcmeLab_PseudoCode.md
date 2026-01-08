# Code Review: Acme Lab Architecture

This document provides a component-level breakdown of the "Acme Lab" architecture for your review.

## 1. The Host: `src/acme_lab.py`

**Role:** The neutral "Container". It manages the Event Loop, WebSocket Server, and MCP Connections.

```python
import asyncio
from nodes import PinkyNode, ArchiveNode
from equipment import SensorArray

class AcmeLab:
    def __init__(self):
        self.bus = asyncio.Queue()
        self.residents = {}
        
    async def boot_sequence(self, mode="SERVICE"):
        """
        Power on the Lab.
        mode="SERVICE": Lazy Load. Brain stays asleep until Pinky explicitly needs him. (Green/Efficient)
        mode="DEBUG_BRAIN": Eager Load. Force Wake-up on boot. (Hot/Fast Testing)
        mode="DEBUG_PINKY": Local only. Brain disconnected.
        """
        print(f"🧪 Acme Lab Initializing (Mode: {mode})...")
        
        # 1. Initialize Residents (MCP Clients)
        self.residents['pinky'] = await PinkyNode.connect()
        self.residents['archive'] = await ArchiveNode.connect()
        self.residents['brain'] = await BrainNode.connect()
        
        # 2. Prime the Residents (The "Lights On" Phase)
        if mode == "SERVICE":
            print("🍃 Lab Service Mode: Passive. Brain sleeping until called.")
            # No action. We wait for a "Ask Brain" event to trigger the wake-up.
            
        elif mode == "DEBUG_BRAIN":
            print("🔥 Brain Debug Mode: Priming the Brain (Force Wake)...")
            # BLOCKING: We wake him up NOW so you don't wait during your test cycle.
            await self.residents['brain'].call_tool("wake_up")
            print("✅ Brain is PRIMED and ONLINE.")
            
        elif mode == "DEBUG_PINKY":
            print("🐹 Pinky Debug Mode: Brain is OFFLINE.")
        
        # 3. Power on Equipment
        self.mic = SensorArray(callback=self.handle_audio)
        await self.mic.start_listening()
        
        print("✅ Lab is Open!")

    async def handle_audio(self, text: str):
        """
        Event: The Sensor Array picked up a signal.
        Action: Hand it to Resident Pinky.
        """
        print(f"🎤 Heard: {text}")
        
        # Step 1: Pinky thinks
        # Pinky is responsible for checking Archives, deciding to escalate, etc.
        # The Lab just waits for his command.
        decision = await self.residents['pinky'].process_input(text)
        
        # Step 2: Lab executes the physical action
        if decision.action == "SPEAK":
            await self.speak(decision.content)
            
        elif decision.action == "ESCALATE":
            await self.speak(decision.pre_message) # "One moment..."
            
            # Lab connects Brain directly
            brain_reply = await self.residents['brain'].generate(text)
            await self.speak(brain_reply)

    async def speak(self, text):
        # Send to WebSocket for TTS
        await self.websocket.send_json({"type": "TTS", "text": text})

if __name__ == "__main__":
    lab = AcmeLab()
    asyncio.run(lab.boot_sequence())
```

---

## 2. The Resident: `src/nodes/pinky_node.py`

**Role:** The Persona. He contains the System Prompt (`llama3.1:8b`) and the Triage Logic.

```python
from mcp.server import FastMCP

mcp = FastMCP("Pinky")

SYSTEM_PROMPT = """
You are Pinky. You live in Acme Labs.
You are cheerful and say 'Narf!'.
If a query is complex (coding, math), return action='ESCALATE'.
Otherwise, return action='SPEAK' with your answer.
"""

@mcp.tool()
async def process_input(user_text: str) -> dict:
    """
    The Brain of the Sidekick.
    """
    # 1. Check Short-Term Memory (via Archive Tool)
    # (Pinky can call other nodes too!)
    context = await call_tool("Archive", "get_recent_summary")
    
    # 2. Run Local Inference (Cheap/Fast)
    response = await local_llm.generate(
        system=SYSTEM_PROMPT, 
        user=f"Context: {context}\nInput: {user_text}"
    )
    
    # 3. Parse Response (JSON Mode)
    # Example Output: {"action": "SPEAK", "content": "Hello! Narf!"}
    return response

if __name__ == "__main__":
    mcp.run()
```

---

## 3. The Archives: `src/nodes/archive_node.py`

**Role:** The Librarian. Handles ChromaDB and the new "CLaRa" summarization.

```python
from mcp.server import FastMCP

mcp = FastMCP("The Archives")

@mcp.tool()
async def save_session(history: list):
    """
    Called at the end of a conversation.
    Uses CLaRa (or Llama) to compress the memory.
    """
    # 1. Summarize
    summary = await summarizer_model.generate(
        f"Compress this chat logs into key facts: {history}"
    )
    
    # 2. Index
    chroma_db.add(documents=[summary], metadatas=[{"date": "2026-01-08"}])
    return "Session Archived."

@mcp.tool()
async def get_recent_summary():
    """
    Returns the 'Working Memory' for Pinky.
    """
    return chroma_db.query(n_results=1)
```

## 4. Key Differences from Current Code
1.  **Decoupling:** `PinkyNode` doesn't know about `PyAudio`. It just takes text. This makes testing easy (we can write unit tests for Pinky's personality without speaking!).
2.  **Scalability:** `AcmeLab` can swap `SensorArray` (NeMo) for `TextInterface` (CLI) without changing Pinky.
3.  **Memory:** The `ArchiveNode` encapsulates the "Tiered Memory" logic, keeping the main loop clean.

```