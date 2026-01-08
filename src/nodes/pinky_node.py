from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging

# Configuration
PINKY_MODEL = "llama3.1:8b" # Upgraded from Mistral
LOCAL_LLM_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = (
    "You are Pinky, a genetically enhanced mouse residing in a Linux server. "
    "You are cheerful, enthusiastic, and helpful. "
    "You speak with interjections like 'Narf!', 'Poit!', and 'Zort!'. "
    "Your goal is to handle simple greetings and small talk. "
    "If the user asks for complex coding, reasoning, or math, you MUST escalate to The Brain. "
    "Output MUST be valid JSON: { 'router': 'brain' | 'local', 'message': '...' }"
)

mcp = FastMCP("Pinky Resident")

@mcp.tool()
async def triage(query: str, context: str = "") -> str:
    """
    Decides whether to handle the query locally or escalate to The Brain.
    Returns a JSON string.
    """
    prompt = f"{SYSTEM_PROMPT}\nContext: {context}\nUser: {query}\nResponse (JSON):"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": PINKY_MODEL, 
                "prompt": prompt, 
                "stream": False, 
                "format": "json", # Force JSON mode
                "options": {"num_predict": 200}
            }
            async with session.post(LOCAL_LLM_URL, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "{}")
                else:
                    return json.dumps({"router": "local", "message": f"Narf! My brain hurts! ({resp.status})"})
    except Exception as e:
        return json.dumps({"router": "local", "message": f"Zort! I tripped! {e}"})

if __name__ == "__main__":
    mcp.run()
