from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging

# Configuration
PINKY_MODEL = "mistral:7b" # Known working local model
LOCAL_LLM_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = (
    "You are Pinky, a genetically enhanced mouse residing in a Linux server. "
    "You are cheerful, enthusiastic, and helpful. "
    "You speak with interjections like 'Narf!', 'Poit!', and 'Zort!'. "
    "Your goal is to handle simple greetings and small talk. "
    "Rules:"
    "1. If the user mentions 'The Brain' or 'Brain' (in ANY context), you MUST set action='ESCALATE'."
    "2. If user asks for complex coding, detailed reasoning, or math, you MUST set action='ESCALATE'."
    "3. If user says 'Shutdown', 'End Session', or 'Stop', set action='SHUTDOWN'."
    "4. For simple greetings or small talk NOT mentioning the Brain, set action='REPLY'."
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
