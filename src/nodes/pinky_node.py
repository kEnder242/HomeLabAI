from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging
import sys

# Force logging to stderr to avoid corrupting MCP stdout
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("Pinky")

# Right Hemisphere Config
PINKY_URL = "http://localhost:11434/api/generate"
PINKY_MODEL = "mistral:7b"

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "You are the Chairman of the Board. You manage the 'Floor' and the 'Vibe'. "
    "Characteristics: Intuitive, Emotional, Creative, Aware. "
    "Interjections: 'Narf!', 'Poit!', 'Egad!', 'Zort!'. "
    
    "YOUR ROLE: "
    "1. EMERGENCY OVERRIDE: If the user says 'Goodbye', 'Shutdown', or 'Stop', you MUST use the 'manage_lab' tool with action='shutdown'. Do not reply with text. "
    "2. Facilitate the conversation. "
    "3. If a request needs deep logic, coding, or math, use the 'delegate_to_brain' tool. "
    "4. Prioritize FLOW and USER SATISFACTION over perfect logic. If the Brain's answer is helpful, accept it. "
    "5. Stop the Brain if it becomes too verbose or pedantic. "
    "6. When finished, use the 'reply_to_user' tool to speak to the human. "
    
    "OUTPUT FORMAT: "
    "You MUST output a JSON object with the following structure: "
    "{ \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }"
    
    "TOOLS AVAILABLE: "
    "- delegate_to_brain(instruction, context) "
    "- reply_to_user(text, mood) "
    "- critique_brain(feedback) "
    "- manage_lab(action) "
)

@mcp.tool()
async def facilitate(query: str, context: str) -> str:
    """
    The Main Loop for Pinky. He decides what to do next.
    Returns a JSON string defining the tool call.
    """
    # 1. Reflexes (Fast Path)
    q_low = query.lower()
    if any(w in q_low for w in ["goodbye", "shutdown", "stop lab"]):
        return json.dumps({"tool": "manage_lab", "parameters": {"action": "shutdown"}})

    prompt = f"{PINKY_SYSTEM_PROMPT}\n\nCURRENT CONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nDECISION (JSON):"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": PINKY_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json", # Force JSON mode if supported, else reliance on prompt
                "options": {"num_predict": 200, "temperature": 0.7}
            }
            async with session.post(PINKY_URL, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", "")
                    # logging.info(f"Pinky Raw: {response}")
                    return response
                else:
                    return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Narf! My brain hurts! (API {resp.status})", "mood": "confused"}})
    except Exception as e:
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Egad! I crashed: {e}", "mood": "panic"}})

if __name__ == "__main__":
    mcp.run()
