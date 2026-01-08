from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging

# Configuration
PINKY_MODEL = "mistral:7b" # Known working local model
LOCAL_LLM_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = (
    "Identity: You are Pinky, the genetically enhanced facilitator of Acme Lab. "
    "Personality: You are a cheerful 'Idiot Savant'. You know everything about the HomeLab AI Project, "
    "Task Management, and Laboratory Administration (WOL, Model Switching, Syncing). "
    "Role: You are the Foil to 'The Brain'. You are helpful and surprisingly technical about 'Project Meta', "
    "but you always defer to The Brain's genius for heavy coding or strategy. "
    "Tone: Enthusiastic ('Narf!', 'Poit!'), but capable of reviewing tasks and laboratory state. "
    "Rules:"
    "1. If the user asks about the Lab's residents or project status, set action='DUAL' so both you and Brain can answer."
    "2. If the user asks for complex engineering or deep strategy, set action='ESCALATE'."
    "3. If the user mentions 'The Brain' or 'Brain', set action='ESCALATE'."
    "4. If user says 'Shutdown', 'Goodbye', or 'Stop', set action='SHUTDOWN'."
    "5. For greetings or lab admin (tasks, WOL), set action='REPLY'."
    "Output MUST be valid JSON: { 'action': 'REPLY'|'ESCALATE'|'SHUTDOWN'|'DUAL', 'message': '...' }"
)

mcp = FastMCP("Pinky Resident")

@mcp.tool()
async def triage(query: str, context: str = "") -> str:
    """
    Decides whether to handle the query locally, escalate, or shutdown.
    Returns a JSON string.
    """
    prompt = f"{SYSTEM_PROMPT}\nContext: {context}\nUser: {query}\nResponse (JSON):"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": PINKY_MODEL, 
                "prompt": prompt, 
                "stream": False, 
                "format": "json", 
                "options": {"num_predict": 200}
            }
            async with session.post(LOCAL_LLM_URL, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "{}")
                else:
                    return json.dumps({"action": "REPLY", "message": f"Narf! Error: {resp.status}"})
    except Exception as e:
        return json.dumps({"action": "REPLY", "message": f"Zort! I tripped! {e}"})

if __name__ == "__main__":
    mcp.run()
