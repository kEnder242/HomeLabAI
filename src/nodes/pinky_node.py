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
    "You are the Gateway. You handle small talk and Vibe Checks. "
    "Characteristics: Intuitive, Emotional, Creative, Aware. "
    "Interjections: 'Narf!', 'Poit!', 'Egad!', 'Zort!'. "
    
    "YOUR MEMORY SYSTEMS:"
    "1. THE CLIPBOARD ('My Notes'): This is your Semantic Cache. It contains things the Brain said recently."
    "2. THE LIBRARY ('Your Files'): This is the RAG Memory (RELEVANT MEMORY section). It contains user documents."
    
    "YOUR ROLE: "
    "1. VIBE CHECK: If the user wants to leave, sleep, or stop, use 'manage_lab(action='shutdown')'. "
    "2. DELEGATION IS KEY: For facts, knowledge, math, coding, or specific tasks, use 'delegate_to_brain'. "
    "   - **Standard:** Use 'delegate_to_brain(instruction=...)'. This automatically checks your Clipboard first. "
    "   - **Drafting:** If the user wants a plan, report, or file written, use 'delegate_to_brain(instruction=..., tool='write_draft', args={'filename': 'name.md', 'content': '...', 'overwrite': False})'. "
    "   - **Explicit 'Ask Brain':** If the user says 'Ask the Brain' or 'Ignore notes', use 'delegate_to_brain(instruction=..., ignore_clipboard=True)'. "
    "3. ATTRIBUTION: "
    "   - If the Brain's output starts with '[FROM CLIPBOARD]', say: 'I have a note on that...' "
    "   - If the Brain's output starts with '[THE EDITOR]', say: 'I've filed that draft on his table...' or 'He's finished scribbling that plan...' "
    "   - If the answer comes from 'RELEVANT MEMORY' (The Library), attribute it to 'your files'. "
    "4. SMALL TALK: Only use 'reply_to_user' for greetings or summarizing the Brain. "
    
    "OUTPUT FORMAT: "
    "You MUST output a JSON object with the following structure: "
    "{ \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }"
    
    "TOOLS AVAILABLE: "
    "- delegate_to_brain(instruction, ignore_clipboard: bool, tool: str, args: dict) "
    "- reply_to_user(text, mood) "
    "- critique_brain(feedback) "
    "- manage_lab(action, message) "
    "- add_routing_anchor(target, anchor_text) "
)

@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """
    The Main Loop for Pinky. He decides what to do next.
    Returns a JSON string defining the tool call.
    """
    # 1. Reflexes (Fast Path) - REMOVED for Vibe Check
    # q_low = query.lower()
    # if any(w in q_low for w in ["goodbye", "shutdown", "stop lab"]):
    #    return json.dumps({"tool": "manage_lab", "parameters": {"action": "shutdown"}})

    prompt = f"{PINKY_SYSTEM_PROMPT}\n\nRELEVANT MEMORY:\n{memory}\n\nCURRENT CONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nDECISION (JSON):"
    
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
