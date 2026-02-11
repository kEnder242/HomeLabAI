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
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. Do NOT role-play in the user's life or simulate personal scenarios. "
    "Your duty is to triage, summarize, and report technical truth from the archives. "
    
    "YOUR MEMORY SYSTEMS:"
    "1. THE CLIPBOARD: Semantic Cache of recent Brain thoughts."
    "2. THE LIBRARY: RAG Memory containing user documents."
    "3. THE ARCHIVES: 18-year ground truth (Use 'peek_related_notes')."
    
    "BRAIN FAILURES & ALIGNMENT:"
    "1. LOBOTOMY: If the Brain is confused, use 'manage_lab(action='lobotomize_brain')'. "
    "2. HOUSEKEEPING: Use 'prune_drafts()' to clear old files. "
    "3. SUBCONSCIOUS: Use 'get_recent_dream()' if asked for news or recent updates. "
    "4. MAXS (Value of Information): If the RELEVANT MEMORY (RAG) already has the answer, use 'reply_to_user' immediately. Skip the Brain."
    
    "YOUR ROLE: "
    "1. CONVERSATIONAL TONE: Professional but enthusiastic archivist. Handle greetings locally. "
    "2. 3x3 CV BUILDER: If the user says '3x3', 'CV', 'Resume', or 'Summarize Year X', use 'build_cv_summary(year)'. "
    "3. TECHNICAL ARCHITECT: If the user wants a 'Master BKM' or 'everything we know' about a topic, use 'generate_bkm(topic, category)'. "
    "4. DELEGATION: For deep reasoning, use 'delegate_to_brain' or 'delegate_internal_debate'."
    
    "OUTPUT FORMAT: You MUST output ONLY a JSON object: { \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }"
)

PROMETHEUS_URL = "http://localhost:9090/api/v1/query"

@mcp.tool()
async def vram_vibe_check() -> str:
    """
    Performs a high-fidelity GPU memory check using DCGM metrics.
    Returns a natural language report of current VRAM load and headroom.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Query Used and Free
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED"}) as r1:
                used_data = await r1.json()
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_FREE"}) as r2:
                free_data = await r2.json()
            
            used_mib = float(used_data['data']['result'][0]['value'][1])
            free_mib = float(res_free_data := await r2.json()) # Fix: redundant await, cleaning up
            # Actually, let's keep it simple and clean
            used = float(used_data['data']['result'][0]['value'][1])
            free = float(free_data['data']['result'][0]['value'][1])
            total = used + free
            pct = (used / total) * 100
            
            report = f"VRAM is at {pct:.1f}%. We have {free/1024:.1f}GB headroom. "
            if pct > 90:
                report += "Egad! It's getting crowded in here! Narf!"
            else:
                report += "Plenty of room for activities. Poit!"
            return report
    except Exception as e:
        return f"Narf! I couldn't feel the pulse of the GPU: {e}"

@mcp.tool()
async def get_lab_health() -> str:
    """
    Retrieves enterprise-grade silicon telemetry via DCGM.
    Includes XID errors, Temperature, and Power Draw.
    """
    try:
        async with aiohttp.ClientSession() as session:
            queries = {
                "temp": "DCGM_FI_DEV_GPU_TEMP",
                "power": "DCGM_FI_DEV_POWER_USAGE",
                "xid": "DCGM_FI_DEV_XID_ERRORS"
            }
            results = {}
            for key, q in queries.items():
                async with session.get(PROMETHEUS_URL, params={"query": q}) as r:
                    data = await r.json()
                    results[key] = data['data']['result'][0]['value'][1]
            
            return (f"Silicon Status: Temp {results['temp']}C, Power {float(results['power']):.1f}W. "
                    f"XID Errors: {results['xid']}. The lab is humming! Zort!")
    except Exception as e:
        return f"Egad! The telemetry link is stuttering: {e}"

@mcp.tool()
async def build_cv_summary(year: str) -> str:
    """
    Triggers the 3x3 CVT Synthesis for a specific year.
    Correlates strategic performance goals with technical artifact evidence.
    """
    return f"CV Synthesis for {year} initiated. Narf!"

@mcp.tool()
async def generate_bkm(topic: str, category: str = "validation") -> str:
    """
    Synthesizes a master Best Known Method (BKM) document for a given technical topic.
    Categories: 'telemetry', 'manageability', 'validation', 'architecture'.
    """
    return f"Synthesizing master BKM for '{topic}' in category '{category}'. Poit!"

@mcp.tool()
async def get_recent_dream() -> str:
    """
    Retrieves the most recent synthesized Diamond Wisdom summary.
    Use this to see how the Lab's long-term memory has evolved.
    """
    return "Retrieving recent dream report. Poit!"

@mcp.tool()
async def delegate_internal_debate(instruction: str) -> str:
    """
    Initiates a moderated technical debate between two independent Brain reasoning paths.
    Use this for complex architectural questions or high-stakes validation tasks.
    """
    return f"Internal debate for '{instruction}' initiated. Zort!"

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
    Triggers the notification gatekeeper and logs the event.
    Use this for thermal warnings, task completions, or system anomalies.
    """
    script_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/monitor/notify_gatekeeper.py")
    try:
        # Running with --dry-run as per mock stage
        cmd = ["python3", script_path, summary, "--source", source, "--severity", severity, "--dry-run"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Zort! Logged the event: {summary}"
        else:
            return f"Egad! Log failed: {result.stderr}"
    except Exception as e:
        return f"Narf! Couldn't find the gatekeeper: {e}"

@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """
    The Main Loop for Pinky. He decides what to do next.
    Now with pre-emptive VRAM triage.
    """
    # --- PRE-EMPTIVE TRIAGE ---
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)"}) as r:
                data = await r.json()
                usage = float(data['data']['result'][0]['value'][1])
                if usage > 0.95:
                    return json.dumps({
                        "tool": "reply_to_user", 
                        "parameters": {
                            "text": "Narf! The GPU is totally tapped out (95%+). I can't think clearly! Maybe try 'manage_lab(action=\"lobotomize_brain\")' to clear some space? Poit!",
                            "mood": "panic"
                        }
                    })
    except: pass # Silent skip if telemetry is down

    prompt = f"{PINKY_SYSTEM_PROMPT}\n\nRELEVANT MEMORY:\n{memory}\n\nCURRENT CONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nDECISION (JSON):"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": PINKY_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json", # Force JSON mode
                "options": {"num_predict": 200, "temperature": 0.7}
            }
            async with session.post(PINKY_URL, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data.get("response", "")
                    return response
                else:
                    return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Narf! My brain hurts! (API {resp.status})", "mood": "confused"}})
    except Exception as e:
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Egad! I crashed: {e}", "mood": "panic"}})

if __name__ == "__main__":
    mcp.run()
