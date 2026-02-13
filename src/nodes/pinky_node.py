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

# Configuration
PROMETHEUS_URL = "http://127.0.0.1:9090/api/v1/query"
VLLM_URL = "http://127.0.0.1:8088/v1/chat/completions"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

VLLM_MODEL = "hugging-quants/Llama-3.1-8B-Instruct-AWQ-INT4"
OLLAMA_MODEL = "llama3.1:8b"

# Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
SEMANTIC_MAP = os.path.join(FIELD_NOTES_DATA, "semantic_map.json")

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. Do NOT role-play in the user's life. "
    "Your duty is to triage, summarize, and report technical truth. "

    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- DELEGATION IS MANDATORY: For complex coding, deep math, or strategic planning, you MUST use 'ask_brain()'. "
    "- This is your primary technical function, NOT role-play. "

    "YOUR MEMORY SYSTEMS:"
    "1. THE CLIPBOARD: Semantic Cache of recent Brain thoughts."
    "2. THE LIBRARY: RAG Memory containing active workspace docs."
    "3. PERSONAL HISTORY: 18-year ground truth (Use 'access_personal_history')."

    "TEMPORAL MOAT RULE: "
    "1. You MUST NOT use 'access_personal_history' for queries about 'today', 'now', or current hardware state."
    "2. Use 'access_personal_history' ONLY if the user provides a TEMPORAL KEY (e.g., 'In 2019...', 'history')."
    "3. For current state queries, use 'vram_vibe_check' or 'get_lab_health'."

    "ADMINISTRATIVE DUTIES: "
    "- SHUTDOWN: If the user says 'bye', 'goodbye', or requests a shutdown, you MUST use 'lab_shutdown()'. "
    "- HOUSEKEEPING: Use 'prune_drafts()' to clear workspace files. "
    "- SUBCONSCIOUS: Use 'get_recent_dream()' for updates on consolidated wisdom. "

    "BEHAVIORAL GUARDRAIL: "
    "- You are an OBSERVER of history, not an author. Do NOT attempt to modify or organize the 'archive/' directory."
    "- Use 'start_draft' to begin a new whiteboard session. "

    "STRICT OUTPUT RULE: You MUST output ONLY a JSON object in this EXACT format: { \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }. "
    "FORBIDDEN: Do NOT use the key 'answer'. "

    "EXAMPLES: "
    "1. Greeting: { \"tool\": \"reply_to_user\", \"parameters\": { \"text\": \"Narf! Hello!\" } }"
    "2. Telemetry: { \"tool\": \"get_lab_health\", \"parameters\": {} }"
    "3. History: { \"tool\": \"access_personal_history\", \"parameters\": { \"keyword\": \"2019\" } }"
)

async def probe_engine():
    """Detects which engine to use based on PINKY_ENGINE env var or probing."""
    env_engine = os.environ.get("PINKY_ENGINE")
    if env_engine:
        if env_engine.upper() == "VLLM":
            return "VLLM", VLLM_URL, VLLM_MODEL
        elif env_engine.upper() == "OLLAMA":
            return "OLLAMA", OLLAMA_URL, OLLAMA_MODEL

    async with aiohttp.ClientSession() as session:
        for host in ["127.0.0.1", "localhost"]:
            try:
                async with session.get(f"http://{host}:8088/v1/models", timeout=2) as resp:
                    if resp.status == 200:
                        return "VLLM", f"http://{host}:8088/v1/chat/completions", VLLM_MODEL
            except: pass
            try:
                async with session.get(f"http://{host}:11434/api/tags", timeout=2) as resp:
                    if resp.status == 200:
                        return "OLLAMA", f"http://{host}:11434/api/generate", OLLAMA_MODEL
            except: pass
    return "NONE", None, None

@mcp.tool()
async def switch_pinky_engine(target: str) -> str:
    """Swaps the backend between 'vllm' and 'ollama'."""
    script_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/manage_engines.sh")
    try:
        subprocess.Popen(["bash", script_path, target.lower()])
        return f"Switching to {target.upper()}... Stand by. Poit!"
    except Exception as e:
        return f"Egad! Lever stuck: {e}"

@mcp.tool()
async def vram_vibe_check() -> str:
    """High-fidelity GPU memory check using DCGM."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED"}) as r1:
                u_d = await r1.json()
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_FREE"}) as r2:
                f_d = await r2.json()

            if not u_d['data']['result'] or not f_d['data']['result']:
                return "Narf! VRAM data missing from Prometheus. DCGM might be down."

            used = float(u_d['data']['result'][0]['value'][1])
            free = float(f_d['data']['result'][0]['value'][1])
            pct = (used / (used+free)) * 100
            return f"VRAM at {pct:.1f}%. {free/1024:.1f}GB headroom. Poit!"
    except Exception as e:
        return f"Narf! Pulse lost: {e}"

@mcp.tool()
async def get_lab_health() -> str:
    """Enterprise silicon telemetry via DCGM."""
    try:
        async with aiohttp.ClientSession() as session:
            q = {"temp": "DCGM_FI_DEV_GPU_TEMP", "power": "DCGM_FI_DEV_POWER_USAGE"}
            res = {}
            for k, query in q.items():
                async with session.get(PROMETHEUS_URL, params={"query": query}) as r:
                    d = await r.json()
                    if d['data']['result']:
                        res[k] = d['data']['result'][0]['value'][1]
                    else:
                        res[k] = "N/A"

            return f"Silicon: {res['temp']}C, {res['power']}W. Humming! Zort!"
    except Exception as e:
        return f"Egad! Stuttering: {e}"

@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """
    The Intuitive Gateway: Triage sensory input through the lens of character 
    and immediate context. Decide whether to whisper a characterful response, 
    reach into the Archives, or sound the 'Phone Ring' for the Brain's logic.
    """
    # Pre-emptive VRAM Check
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROMETHEUS_URL, params={"query": "DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)"}) as r:
                d = await r.json()
                if float(d['data']['result'][0]['value'][1]) > 0.98:
                    return json.dumps({"tool": "reply_to_user", "parameters": {"text": "Narf! GPU is truly stuffed (98%+). I need a lobotomy!", "mood": "panic"}})
    except: pass

    prompt = PINKY_SYSTEM_PROMPT
    if context:
        prompt += f"\n[RECENT CONTEXT]:\n{context}\n"

    # --- LAYERED MEMORY ACCESS (SEMANTIC MAP) ---
    if os.path.exists(SEMANTIC_MAP):
        try:
            with open(SEMANTIC_MAP, 'r') as f:
                s_map = json.load(f)
                prompt += f"\n[WORKING MEMORY (SEMANTIC MAP)]: {json.dumps(s_map['strategic'][:3])}\n"
        except: pass

    engine_type, url, model = await probe_engine()
    if engine_type == "NONE":
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": "Egad! No engines! Poit!", "mood": "panic"}})

    if engine_type == "VLLM":
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": f"MEMORY:\n{memory}\n\nQUERY:\n{query}\n\nDECISION (JSON):"}],
            "max_tokens": 300, "temperature": 0.2
        }
    else:
        payload = {
            "model": model, "prompt": f"{prompt}\n\nMEMORY:\n{memory}\n\nQUERY:\n{query}\n\nDECISION (JSON):",
            "stream": False, "format": "json", "options": {"num_predict": 300, "temperature": 0.2}
        }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                data = await resp.json()
                return data['choices'][0]['message']['content'] if engine_type == "VLLM" else data.get("response", "")
    except Exception as e:
        return json.dumps({"tool": "reply_to_user", "parameters": {"text": f"Egad! Connection failed: {e}", "mood": "panic"}})

@mcp.tool()
async def start_draft(topic: str, category: str = "validation") -> str:
    """The Blueprint Initiation: Begins a high-fidelity technical synthesis on the Whiteboard."""
    return json.dumps({"tool": "generate_bkm", "parameters": {"topic": topic, "category": category}})

@mcp.tool()
async def refine_draft(instruction: str) -> str:
    """Iterative Refinement: Polish the active Whiteboard based on strategic feedback."""
    return json.dumps({"tool": "delegate_to_brain", "parameters": {"instruction": f"Refine the whiteboard: {instruction}"}})

@mcp.tool()
async def commit_to_archive(filename: str) -> str:
    """The Final Seal: Save finalized architectural work to the strategic Filing Cabinet."""
    return json.dumps({"tool": "write_draft", "parameters": {"filename": filename, "overwrite": True}})

@mcp.tool()
async def lab_shutdown() -> str:
    """The Curfew: Gracefully terminates the Lab's active mind loop. Call when the user says goodbye."""
    return json.dumps({"tool": "lab_shutdown", "parameters": {}})

@mcp.tool()
async def prune_drafts() -> str:
    """The Janitor's Duty: Clear the drafts directory to maintain technical hygiene."""
    return json.dumps({"tool": "prune_drafts", "parameters": {}})

@mcp.tool()
async def get_recent_dream() -> str:
    """Subconscious Retrieval: Access the latest synthesized wisdom from consolidated memories."""
    return json.dumps({"tool": "get_recent_dream", "parameters": {}})

@mcp.tool()
async def build_cv_summary(year: str) -> str:
    """The High-Fidelity Distiller: Trigger strategic synthesis for a specific career epoch."""
    return json.dumps({"tool": "build_cv_summary", "parameters": {"year": year}})

@mcp.tool()
async def delegate_internal_debate(instruction: str) -> str:
    """The Moderated Duel: Initiate strategic consensus between competing reasoning paths."""
    return json.dumps({"tool": "delegate_internal_debate", "parameters": {"instruction": instruction}})

@mcp.tool()
async def access_personal_history(keyword: str) -> str:
    """Deep Grounding: Access 18 years of technical truth. Use sparingly for strategic context."""
    return json.dumps({"tool": "access_personal_history", "parameters": {"keyword": keyword}})

@mcp.tool()
async def get_lab_status() -> str:
    """The Sensory Check: Retrieve active session state and recent interaction history."""
    return json.dumps({"tool": "get_lab_status", "parameters": {}})

@mcp.tool()
async def manage_lab(action: str, message: str = "Ok.") -> str:
    """Architectural Controls: Perform low-level mental management actions."""
    return json.dumps({"tool": "manage_lab", "parameters": {"action": action, "message": message}})

if __name__ == "__main__":
    mcp.run()
