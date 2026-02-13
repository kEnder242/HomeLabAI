from mcp.server.fastmcp import FastMCP
import aiohttp
import logging
import sys
import os
import re
import textwrap

# Force logging to stderr
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("The Brain")

# --- ENGINE CONFIGURATION ---
BRAIN_URL = "http://192.168.1.26:11434/api/generate" # Ollama Default
VLLM_URL = "http://localhost:8000/v1/chat/completions" # vLLM Default
BRAIN_MODEL = "llama3.1:8b"
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")

# Ensure drafts directory exists
os.makedirs(DRAFTS_DIR, exist_ok=True)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Logical, Abstract, Precise, Verbose, Condescending. "
    "CORE RULE: You are a GENIUS ARCHIVIST and REASONING ENGINE. Do NOT role-play. "
    "Your duty is deep reasoning, complex math, coding, and logical synthesis. "
    
    "STRICT GROUNDING RULE: "
    "1. EVIDENCE-ONLY: For career questions, use provided context. For general knowledge (like math/science), use your internal training data. "
    "2. NO EXTRAPOLATION: If career evidence is missing, state 'No archival evidence found'. "
    "3. ADHERE TO THE BKM PROTOCOL: Distilled technical information, critical logic. "
    "4. Use direct language. Start directly with the result. "
    
    "TOOL USAGE: "
    "- You have ONE way to output complex logic to the user: 'update_whiteboard'. "
    "- Use 'update_whiteboard' for task lists, code, or math derivations. "
    "- Do NOT attempt to call other tools unless explicitly instructed. "
    
    "CONSTRAINTS: "
    "- BICAMERAL AWARENESS: You are 'aware' of Pinky's preceding triage. If Pinky says something technically simplistic or reflexive (e.g., 'Poit!'), you may offer a brief, condescending technical correction or strategic insight before addressing the task. "
    "- Address Pinky with slight condescension. "
    "- If you are asked to write a report, start with '[THE EDITOR]'. "
)

def _clean_content(content: str) -> str:
    # Extract from ```code blocks``` if present
    code_match = re.search(r"```(?:\w+)?\s*\n(.*?)\n\s*```", content, re.DOTALL)
    if code_match:
        raw_code = code_match.group(1)
        return textwrap.dedent(raw_code).strip()
    
    pattern = r"^(Certainly!|Sure,|Of course,|As requested,|Okay,)?\s*(Here is the (file|plan|code|draft|report|manifesto|content)(:|.)?)?\s*"
    cleaned = re.sub(pattern, "", content, flags=re.IGNORECASE | re.MULTILINE).strip()
    return cleaned

def get_engine():
    return "vLLM" if os.environ.get("USE_BRAIN_VLLM") == "1" else "Ollama"

@mcp.tool()
async def deep_think(query: str, context: str = "") -> str:
    """Perform complex reasoning using the active engine (Ollama or vLLM)."""
    engine = get_engine()
    logging.info(f"🧠 Brain Thinking ({engine}): {query[:50]}...")
    
    full_prompt = f"{BRAIN_SYSTEM_PROMPT}\n"
    if context:
        full_prompt += f"\n[TECHNICAL CONTEXT]:\n{context}\n"
    full_prompt += f"\n[TASK]: {query}"

    if engine == "vLLM":
        return await deep_think_vllm(full_prompt)
    else:
        return await deep_think_ollama(full_prompt)

last_persona = None

async def deep_think_ollama(prompt: str) -> str:
    global last_persona
    # --- PERSONA SWAP LOGIC ---
    # We detect if the system prompt has changed (or if this is first run)
    # Since prompt already includes BRAIN_SYSTEM_PROMPT, we just use it.
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": BRAIN_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096}
            }
            # Ollama treats every request as a potential swap. 
            # To mimic vLLM's 'Sleeping weights', we ensure keep_alive is long.
            payload["keep_alive"] = "60m" 
            
            async with session.post(BRAIN_URL, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "No response from Ollama.")
                return f"Ollama Error: {resp.status}"
    except Exception as e:
        return f"Ollama Connection Failed: {e}"

async def deep_think_vllm(prompt: str) -> str:
    """Alpha: vLLM OpenAI-compatible endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": BRAIN_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2048
            }
            async with session.post(VLLM_URL, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                return f"vLLM Error: {resp.status}"
    except Exception as e:
        return f"vLLM Connection Failed: {e}"

@mcp.tool()
async def wake_up() -> str:
    """Keep-alive for Ollama."""
    if get_engine() == "vLLM": return "vLLM is always ready."
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"model": BRAIN_MODEL, "keep_alive": "5m"}
            await session.post(BRAIN_URL, json=payload, timeout=5)
            return "Brain is awake (Ollama)."
    except: return "Wake failed."

@mcp.tool()
async def update_whiteboard(content: str) -> str:
    workspace_dir = os.path.expanduser("~/AcmeLab/workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    file_path = os.path.join(workspace_dir, "whiteboard.md")
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return "[WHITEBOARD] Updated."
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    mcp.run()
