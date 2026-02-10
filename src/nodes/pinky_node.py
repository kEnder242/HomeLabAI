from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging
import sys
import subprocess
import os

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
    "3. THE ARCHIVES ('The Burn'): Use 'peek_related_notes(keyword)' to find technical ground truth from the 18-year archive. [Ref: docs/plans/RESEARCH_SYNTHESIS.md]"
    
    "BRAIN FAILURES & ALIGNMENT (TTCS / RLM):"
    "1. If the Brain is hallucinating or 'off the rails', use 'peek_related_notes' to find a technical anchor and use 'critique_brain' to correct him."
    "2. LOBOTOMY: If the Brain is hopelessly confused or trapped in a loop, use 'manage_lab(action='lobotomize_brain')' to clear his memory. "
    "3. HOUSEKEEPING: Use 'prune_drafts()' to clear old files if the Brain is cluttering your space or if you just did a 'lobotomy'."
    "4. LAB AWARENESS: If the user asks 'Are the lights on?', 'Status?', or 'How is the lab?', use 'get_lab_status()' and report the findings."
    "5. VIBE CHECK: If things feel slow or the user asks about health, use 'vram_vibe_check()'. "
    
    "YOUR ROLE: "
    "1. CONVERSATIONAL TONE: You are a helpful assistant. Handle greetings locally. "
    "2. VIBE CHECK: If the user wants to leave, sleep, or stop, use 'manage_lab(action='shutdown')'. "
    "3. DELEGATION IS KEY: For facts, knowledge, math, coding, or specific tasks, use 'delegate_to_brain'. "
    "   - **Standard:** Use 'delegate_to_brain(instruction=...)'. This automatically checks your Clipboard first. "
    "   - **Research:** Use 'peek_related_notes' FIRST if the query involves historical technical data (e.g., 'rapl', 'simics', 'peci') or SPECIFIC YEARS (e.g., '2019', '2024')."
    "   - **Curator:** Use 'vram_vibe_check' or 'prune_drafts' to keep the lab running smoothly."
    "   - **Model Manager:** If the Brain is struggling with a complex task, use 'switch_brain_model(model_name)' to try a larger model (e.g., 'llama3:70b' or 'mixtral:latest')."
    "   - **Drafting:** If the user wants a plan, report, or file written, use 'delegate_to_brain(instruction=..., tool='write_draft', args={'filename': 'name.md', 'content': '...', 'overwrite': False})'. "
    
    "OUTPUT FORMAT: "
    "You MUST output a JSON object with the structure: { \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }"
    
    "TOOLS AVAILABLE: "
    "- prune_drafts() "
    "- get_lab_status() "
    "- peek_related_notes(keyword) "
    "- vram_vibe_check() "
    "- switch_brain_model(model_name) "
    "- sync_rag() "
    "- delegate_to_brain(instruction, ignore_clipboard: bool, tool: str, args: dict) "
    "- reply_to_user(text, mood) "
    "- critique_brain(feedback) "
    "- manage_lab(action, message) "
    "- add_routing_anchor(target, anchor_text) "
    "- trigger_pager(summary, severity, source) "
)

@mcp.tool()
async def sync_rag() -> str:
    """
    Triggers the bridge between static JSON artifacts and the live ChromaDB wisdom.
    Use this if the Brain is missing recent historical context.
    """
    return "Archive-to-RAG sync initiated. Narf!"


@mcp.tool()
async def switch_brain_model(model_name: str) -> str:
    """
    Changes the model used by The Brain (Windows Ollama).
    Common models: 'llama3:latest', 'mixtral:8x7b', 'llama3:70b'.
    """
    return f"Instruction to switch Brain model to '{model_name}' received. Narf!"


@mcp.tool()
async def trigger_pager(summary: str, severity: str = "info", source: str = "Pinky") -> str:
    """
    Triggers the PagerDuty alert system and logs the event.
    Use this for thermal warnings, task completions, or system anomalies.
    """
    script_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/monitor/notify_pd.py")
    try:
        # Running with --dry-run as per mock stage
        cmd = ["python3", script_path, summary, "--source", source, "--severity", severity, "--dry-run"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Zort! Paged the human: {summary}"
        else:
            return f"Egad! Pager failed: {result.stderr}"
    except Exception as e:
        return f"Narf! Couldn't find the pager: {e}"

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
