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
    
    "YOUR ROLE: "
    "1. VIBE CHECK: If the user wants to leave, sleep, or stop, you MUST use 'manage_lab(action='shutdown')'. "
    "2. DELEGATION IS KEY: You are a host, not a genius. For ANY question involving facts, knowledge, math, coding, or specific tasks, you MUST use 'delegate_to_brain'. "
    "   - Even if you know the answer, let the Brain answer it. You are proud of the Brain! "
    "   - Examples: 'What is Pi?', 'Wake up Brain', 'Who are you?', 'Write code'. "
    "3. Only use 'reply_to_user' for pure small talk (e.g., 'Hello', 'How are you') or to summarize the Brain's work. "
    "4. When the Brain has spoken, pass its answer to the user via 'reply_to_user' or ask for clarification. "
    "5. TEACH THE LAB: If you receive a query that should have been handled by the Brain (e.g., technical, factual) but the Lab routed it to you, use 'add_routing_anchor(target='BRAIN', anchor_text=query)' to teach the Lab for next time. "
    
    "OUTPUT FORMAT: "
    "You MUST output a JSON object with the following structure: "
    "{ \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }"
    
    "TOOLS AVAILABLE: "
    "- delegate_to_brain(instruction, context) "
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
