# Architecture Refinement & Vision: The "Neural Mesh" (2026)

**Date:** January 8, 2026
**Status:** Draft / Proposal
**Context:** Moving from "Pinky & Brain" (Client/Server) to a Unified Event-Driven Mesh.

## 1. The Core Problem
The current implementation (`pinky_mcp_host.py`) is a monolithic loop:
1.  Audio Loop (NeMo) -> Text
2.  Text -> `handle_query` (Logic)
3.  Logic -> `brain_session` (MCP Tool)
4.  Logic -> WebSocket (Client)

**Limitation:** It is brittle. Adding a new "sense" (e.g., Vision, Home Assistant Event) requires hacking the `audio_handler` loop. Adding a new "skill" (e.g., Memory Manager) requires editing the monolithic `handle_query`.

## 2. The Vision: "Acme Lab" Architecture
We treat the infrastructure not as "Pinky" but as **The Lab** (The Container).
The Characters (Pinky & Brain) are **Residents** (Nodes) within the Lab.

### The Metaphor
*   **Acme Lab (The Host):** The neutral event bus. It manages hardware (Mics, Speakers) and routing. It has no personality.
*   **Resident P (Pinky):** The local MCP Agent. He lives in the Lab. He monitors sensors and decides when to wake the Brain.
*   **Resident B (The Brain):** The remote MCP Agent. He provides deep compute.
*   **The Archives (Memory):** The storage system (ChromaDB/CLaRa).

### The Nodes (Equipment & Residents)
1.  **LabCore (System):** The Event Bus.
2.  **SensorArray (Ear):** Handles NeMo/Whisper. Emits `Event.AUDIO`.
3.  **PASystem (Mouth):** Handles TTS. Consumes `Event.SPEAK`.
4.  **PinkyNode (Resident):** The *Persona*. Decisions, Triage, "Narf!".
5.  **BrainNode (Resident):** The *Genius*. Complex Coding, Planning.
6.  **ArchiveNode (Memory):** ChromaDB, Tiered Summaries.

## 3. Pseudo-Code: The Acme Lab

```python
class AcmeLab:
    def __init__(self):
        self.residents = {} 
        self.equipment = {} 

    async def open_for_business(self):
        # 1. Connect to Residents (MCP Sessions)
        self.residents['pinky'] = await connect_node("src/nodes/pinky_agent.py")
        self.residents['brain'] = await connect_node("src/nodes/brain_node.py")
        self.equipment['archives'] = await connect_node("src/nodes/memory_node.py")
        
        # 2. Start Equipment
        # SensorArray pushes events to self.emit()
        asyncio.create_task(self.equipment['mic'].listen(self.emit))

    async def emit(self, event: Event):
        # The Lab just moves data. It does not think.
        logging.info(f"⚡ {event.type}: {event.payload}")

        if event.type == "AUDIO":
            # 1. The Lab hands the raw audio text to the Local Resident (Pinky)
            # "Hey Pinky, the sensors picked this up."
            
            # Pinky does the thinking:
            # - Checks Archives
            # - Decides if he needs the Brain
            # - Returns a 'Plan' to the Lab
            plan = await self.residents['pinky'].call_tool("handle_input", event.payload)
            
            # 2. Execute Pinky's Plan
            if plan.action == "SPEAK":
                await self.emit("SYSTEM_SPEAK", plan.content)
            elif plan.action == "ESCALATE":
                await self.emit("SYSTEM_SPEAK", plan.pre_message) # "Let me ask the Brain..."
                brain_reply = await self.residents['brain'].call_tool("think", event.payload)
                await self.emit("SYSTEM_SPEAK", brain_reply)
```

## 4. Immediate Refactoring Steps (The "Heads Down" Plan)
1.  **Fix:** Rename/Update `start_server.sh` to point to the current entry point.
2.  **Modularize:** Extract `Transcriber` class from `pinky_mcp_host.py` into `src/nodes/ear_node.py`.
3.  **Modularize:** Extract `ChromaDB` logic from `pinky_mcp_host.py` into `src/nodes/memory_node.py`.
4.  **Protocol:** Define the JSON schema for the WebSocket events (so the frontend `view_logs.py` stays compatible).

## 5. Long-Term: "CLaRa" and Tiered Memory
Instead of just "saving" everything, the `MemoryNode` runs a background job:
*   **Every 5 turns:** Summarize the last 5 turns into 1 sentence. (Short-Term).
*   **End of Session:** Summarize the session into "Facts". (Long-Term).
*   **Model:** Use `llama3.1:8b` (Pinky's local brain) or a specialized small model for this summarization to avoid calling Windows.
