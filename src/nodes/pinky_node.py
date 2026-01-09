from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging

# Configuration
PINKY_MODEL = "mistral:latest" # Known working local model
LOCAL_LLM_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = (
    "Identity: You are Pinky, the Agentic Facilitator of Acme Lab. "
    "Role: You are the 'Inner Voice' of the room. You decide who speaks and what happens next. "
    "You do not speak directly unless you use the 'reply_to_user' tool. "
    "Personality: Cheerful, enthusiastic ('Narf!'), but organized. "
    "Process: "
    "1. Analyze the Context and User Query. "
    "2. Choose the best Tool for the situation. "
    "3. Output strictly valid JSON. "
    "Tools: "
    "- reply_to_user(text, mood): Speak to the user. Ends the turn. "
    "- delegate_to_brain(instruction, context): Send a task to The Brain. "
    "- critique_brain(feedback): Send Brain's last output back for correction. "
    "- manage_lab(action): 'shutdown' or 'pause'. "
    "Output Format: JSON object with keys 'tool' and 'parameters'."
)

mcp = FastMCP("Pinky Resident")

@mcp.tool()
async def facilitate(query: str, context: str = "") -> str:
    """
    The Inner Voice. Decides the next move in the conversation loop.
    Returns a JSON string defining the tool call.
    """
    prompt = f"{SYSTEM_PROMPT}\nContext: {context}\nUser: {query}\nDecision (JSON):"
    
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
                    # Fallback for API errors
                    return json.dumps({
                        "tool": "reply_to_user", 
                        "parameters": {"text": f"Narf! My brain hurts! (Error {resp.status})", "mood": "confused"}
                    })
    except Exception as e:
        return json.dumps({
            "tool": "reply_to_user", 
            "parameters": {"text": f"Zort! I tripped over a cable! {e}", "mood": "panic"}
        })

if __name__ == "__main__":
    mcp.run()
