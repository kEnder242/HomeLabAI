from mcp.server.fastmcp import FastMCP
import aiohttp
import json
import logging
import sys
import subprocess
import os
import time

# Force logging to stderr to avoid corrupting MCP stdout
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("Pinky")

# Configuration
PROMETHEUS_URL = "http://localhost:9090/api/v1/query"
VLLM_URL = "http://localhost:8088/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"

VLLM_MODEL = "TheBloke/Mistral-7B-Instruct-v0.2-AWQ"
OLLAMA_MODEL = "mistral:7b"

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
    "1. LOBOTOMY: If the Brain is confused, use 'manage_lab(action=\"lobotomize_brain\")'. "
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

async def probe_engine():
    """Detects which engine is currently running on the local node."""
    async with aiohttp.ClientSession() as session:
        # Check vLLM first (Port 8088)
        try:
            async with session.get("http://localhost:8088/v1/models", timeout=1) as resp:
                if resp.status == 200:
                    return "VLLM", VLLM_URL, VLLM_MODEL
        except: pass

        # Check Ollama (Port 11434)
        try:
            async with session.get("http://localhost:11434/api/tags", timeout=1) as resp:
                if resp.status == 200:
                    return "OLLAMA", OLLAMA_URL, OLLAMA_MODEL
        except: pass

    return "NONE", None, None

@mcp.tool()
async def switch_pinky_engine(target: str) -> str:
    """
    Swaps the backend LLM engine between 'vllm' and 'ollama'.
    This manages VRAM by stopping the unused service.
    """
    script_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/manage_engines.sh")
    if target.lower() not in ["vllm", "ollama"]:
        return "Narf! Target must be 'vllm' or 'ollama'. Poit!"
    
    try:
        # Fire and forget the management script to avoid blocking Pinky
        subprocess.Popen(["bash", script_path, target.lower()])
        return f"Switching to {target.upper()}... Stand by while I recalibrate my VRAM. Poit!"
    except Exception as e:
        return f"Egad! The engine lever is stuck: {e}"

@mcp.tool()
async def vram_vibe_check() -> str:
    """
    Performs a high-fidelity GPU memory check using DCGM metrics.
    Returns a natural language report of current VRAM load and headroom.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED"}) as r1:
                used_data = await r1.json()
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_FREE"}) as r2:
                free_data = await r2.json()
            
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
            queries = {"temp": "DCGM_FI_DEV_GPU_TEMP", "power": "DCGM_FI_DEV_POWER_USAGE", "xid": "DCGM_FI_DEV_XID_ERRORS"}
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
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """Main interaction loop with auto-detecting backend support."""
    # 1. Pre-emptive VRAM Triage
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)"}) as r:
                data = await r.json()
                usage = float(data['data']['result'][0]['value'][1])
                if usage > 0.95:
                    return json.dumps({"tool": "reply_to_user", "parameters": {"text": "Narf! GPU is tapped out (95%+). Try 'lobotomize_brain' first!", "mood": "panic"}})
    except: pass

    # 2. Detect Engine
    engine_type, url, model = await probe_engine()
    if engine_type == "NONE":
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": "Egad! Both vLLM and Ollama are offline. I am floating in a void! Poit!", "mood": "panic"}})

    # 3. Construct Payload
    if engine_type == "VLLM":
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": PINKY_SYSTEM_PROMPT},
                {"role": "user", "content": f"RELEVANT MEMORY:\n{memory}\n\nCONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nDECISION (JSON):"}
            ],
            "max_tokens": 300, "temperature": 0.7, "stream": False
        }
    else: # OLLAMA
        prompt = f"{PINKY_SYSTEM_PROMPT}\n\nRELEVANT MEMORY:\n{memory}\n\nCONTEXT:\n{context}\n\nUSER QUERY:\n{query}\n\nDECISION (JSON):"
        payload = {
            "model": model, "prompt": prompt, "stream": False, "format": "json",
            "options": {"num_predict": 300, "temperature": 0.7}
        }

    # 4. Execute
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data['choices'][0]['message']['content'] if engine_type == "VLLM" else data.get("response", "")
                    return response
                else:
                    return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Narf! {engine_type} error: {resp.status}", "mood": "confused"}})
    except Exception as e:
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Egad! {engine_type} connection failed: {e}", "mood": "panic"}})

# --- Legacy Tools Stubs ---
@mcp.tool()
async def build_cv_summary(year: str) -> str: return f"CV Synthesis for {year} initiated. Narf!"
@mcp.tool()
async def generate_bkm(topic: str, category: str = "validation") -> str: return f"Synthesizing BKM for '{topic}'. Poit!"
@mcp.tool()
async def get_recent_dream() -> str: return "Retrieving recent dream report. Poit!"
@mcp.tool()
async def delegate_internal_debate(instruction: str) -> str: return f"Internal debate for '{instruction}' initiated. Zort!"
@mcp.tool()
async def sync_rag() -> str: return "Archive-to-RAG sync initiated. Narf!"
@mcp.tool()
async def switch_brain_model(model_name: str) -> str: return f"Brain model set to '{model_name}'. Narf!"
@mcp.tool()
async def trigger_pager(summary: str, severity: str = "info", source: str = "Pinky") -> str:
    script_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/monitor/notify_gatekeeper.py")
    subprocess.run(["python3", script_path, summary, "--source", source, "--severity", severity, "--dry-run"])
    return f"Logged: {summary}"

if __name__ == "__main__":
    mcp.run()