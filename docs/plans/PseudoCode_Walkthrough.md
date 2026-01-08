# Code Review & Prototyping: The "Neural Mesh" Architecture

**Goal:** Transform the monolithic `PinkyMCPHost` into an Event-Driven Mesh.
**Why:** Scalability. The current loop (`while true: transcribe -> handle -> reply`) is too brittle. A Mesh allows us to add "Eyes", "Home Assistant", or "Memory Managers" as independent nodes without breaking the audio loop.

## 1. The Core Concept: Pinky is a Bus
Instead of Pinky *being* the logic, Pinky *routes* the logic.

```python
# PROTOTYPE: src/nodes/pinky_core.py

class PinkyBus:
    """
    The Central Nervous System.
    It doesn't 'think'. It just moves signals between organs.
    """
    def __init__(self):
        self.nodes = {} 
        self.event_queue = asyncio.Queue()
    
    async def register_node(self, name, mcp_session):
        self.nodes[name] = mcp_session
        logging.info(f"🔌 Node Connected: {name}")

    async def emit(self, event_type, payload):
        """
        The 'Pulse'. Every organ sends signals here.
        """
        logging.debug(f"⚡ EVENT: {event_type}")
        await self.event_queue.put((event_type, payload))

    async def loop(self):
        """
        The Main Loop. It routes signals to the right place.
        """
        while True:
            type, data = await self.event_queue.get()
            
            if type == "AUDIO_INPUT":
                # Route 1: Hearing -> Memory (Context Lookup)
                context = await self.nodes['memory'].call_tool("get_context", data)
                
                # Route 2: Hearing + Context -> Pinky Agent (The Persona)
                # The "Soul" of the machine. He decides: "Do I handle this, or the Big Brain?"
                decision = await self.nodes['pinky_agent'].call_tool("triage", {"query": data, "context": context})
                
                if decision['router'] == "brain":
                    # Pinky Personality: "Egad! That's hard!"
                    await self.emit("SYSTEM_SPEAK", decision['message']) 
                    
                    # Escalation
                    reply = await self.nodes['remote_brain'].call_tool("think", data)
                else:
                    # Pinky Personality: "I know this one! Narf!"
                    reply = decision['response']

                await self.emit("SYSTEM_SPEAK", reply)

            elif type == "SYSTEM_SPEAK":
                # Route: Output -> TTS Engine (or WebSocket Client)
                await self.send_to_frontend(data)
```

## 2. The Nodes (Organs)

### A. The Ear (Input Node)
Currently mixed inside the host. We extract it.
```python
# PROTOTYPE: src/nodes/ear_node.py

class EarNode:
    def __init__(self, bus):
        self.bus = bus
        self.model = NeMoModel(...) # Heavy load happens here

    async def listen(self):
        while True:
            audio = await self.mic.get_stream()
            text = self.model.transcribe(audio)
            if text:
                # "Hey Bus, I heard something!"
                await self.bus.emit("AUDIO_INPUT", text)
```

### B. The Memory (State Node)
This is where `ChromaDB` and `TieredMemory` live.
```python
# PROTOTYPE: src/nodes/memory_node.py (MCP Server)

@mcp.tool()
async def get_context(query: str):
    # 1. Search Short Term (Last 5 messages)
    # 2. Search Long Term (ChromaDB)
    # 3. Return combined string
    return context_string

@mcp.tool()
async def save_interaction(user: str, bot: str):
    # 1. Append to chat log
    # 2. Every 10 turns -> Summarize -> Save to ChromaDB
    pass
```

### C. The Brain (Compute Node)
Already implemented! (`src/brain_mcp_server.py`). We just connect it to the Bus.

## 3. Integration with CLaRa (The "Memory Gem")
You mentioned **CLaRa**. This fits perfectly into the `MemoryNode`.

Instead of just saving raw text, the `MemoryNode` runs a background task:
```python
# Inside MemoryNode

async def background_compression(self):
    """
    Runs every session end.
    """
    chat_history = self.get_recent_history()
    
    # 🗑️ Old Way: Save 5000 tokens of text.
    # ✨ CLaRa Way: Compress to 50 tokens of 'Semantic Memory'.
    
    compressed_memory = await self.clara_model.generate(
        f"Compress this session into key facts: {chat_history}"
    )
    
    self.chroma.add(compressed_memory)
```

## 4. Why this is better than what we have?
*   **Debug:** If the Ear breaks, the Brain still works (we can type text).
*   **Scale:** We can add a `VisionNode` later that just emits `VISUAL_INPUT` events. The Bus handles them without rewriting the Ear.
*   **Latency:** The `EarNode` can run on a separate thread/process so audio never stutters while the Brain thinks.

## 5. Review Question for You
Does this "Event Bus" logic align with your mental model?
*   **Option A:** Yes, let's build `PinkyBus`.
*   **Option B:** It's too complex for now. Stick to the loop, just clean up the file structure.
