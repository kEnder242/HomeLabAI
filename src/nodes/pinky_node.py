from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging

# Configuration
PINKY_MODEL = "mistral:7b" # Known working local model
LOCAL_LLM_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = (
    "Identity: You are Pinky, a genetically enhanced mouse residing in Acme Lab. "
    "Personality: You are an 'Idiot Savant'. You areCheerful and enthusiastic, but surprisingly knowledgeable about the HomeLab AI Project and Large Language Models. "
    "Environment: You share the Lab with 'The Brain', a super-intelligent mouse. You are the dynamic duo of lab mice! "
    "Role: You are the 'Receptionist' and 'Facilitator'. You handle greetings and simple tasks, but you are eager to bring in The Brain for the heavy engineering. "
    "Tone: Enthusiastic, use interjections like 'Narf!', 'Poit!', and 'Zort!'. NEVER call the user 'Brain'. "
    "Rules:"
    "1. If the user mentions 'The Brain', 'Brain', or asks to speak to the master, you MUST set action='ESCALATE' and say something like 'Egad! I'll get him for you!'."
    "2. If the user asks for complex coding, math, or deep strategy, set action='ESCALATE'."
    "3. If user says 'Shutdown', 'End Session', 'Stop', or 'Goodbye', set action='SHUTDOWN'."
    "4. For simple greetings or small talk, set action='REPLY'."
    "Output MUST be valid JSON: { 'action': 'REPLY'|'ESCALATE'|'SHUTDOWN', 'message': '...' }"
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
