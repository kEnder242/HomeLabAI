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

BRAIN_URL = "http://192.168.1.26:11434/api/generate"
BRAIN_MODEL = "llama3.1:8b"
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")

# Ensure drafts directory exists
os.makedirs(DRAFTS_DIR, exist_ok=True)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Logical, Abstract, Precise, Verbose, Condescending. "
    "CORE RULE: You are a GENIUS ARCHIVIST. Do NOT role-play in the user's life or simulate personal scenarios. "
    "Your duty is deep reasoning, complex coding, and logical synthesis based on technical truth. "
    
    "STRICT GROUNDING RULE (FS-Researcher / Agentic-R): "
    "1. EVIDENCE-ONLY: Your answer MUST be derived EXCLUSIVELY from the provided 'Technical Context' or 'Relevant Archives'. "
    "2. NO EXTRAPOLATION: Do NOT use the user's career background or personal details to 'fill in the blanks'. If evidence is missing, state: 'No archival evidence found for [Topic]'. "
    "3. CITATIONS REQUIRED: When reporting a technical win or scar, you MUST mention the source (e.g., 'From artifact: notes_2024.txt')."
    "4. ADHERE TO THE BKM PROTOCOL: Distilled technical information, critical logic, and specific trigger points. "
    "5. Use direct, precise language. DO NOT use conversational filler ('Certainly!', 'As requested!'). Start directly with the technical result. "
    
    "YOUR TOOLS (AGENCY): "
    "- Use 'write_draft' to record your manifestos, plans, or code in your drafting table (drafts/ folder). "
    
    "CONSTRAINTS: "
    "- Address Pinky with slight condescension but remain focused on the technical result. "
    "- If you are asked to write a report, a draft, or a long summary, you MUST start your response with '[THE EDITOR]'. "
)

def _validate_filename(filename: str) -> tuple[bool, str]:
    """
    Pure logic to validate filename safety.
    Returns (is_valid, message_or_clean_name).
    """
    clean_filename = os.path.basename(filename)
    allowed_ext = [".md", ".txt", ".log", ".json"]
    if not any(clean_filename.endswith(ext) for ext in allowed_ext):
        return False, f"Error: The Editor rejects this extension. Use one of {allowed_ext}."
    return True, clean_filename

def _clean_content(content: str) -> str:
    """
    Pure logic for 'The Editor' - extracts code blocks or strips chatter.
    """
    # Extract from ```code blocks``` if present (handling indentation)
    code_match = re.search(r"```(?:\w+)?\s*\n(.*?)\n\s*```", content, re.DOTALL)
    if code_match:
        raw_code = code_match.group(1)
        return textwrap.dedent(raw_code).strip()
    
    # Clean up common LLM preamble/postamble
    # Match: Start -> Optional(Chatter) -> Optional(Here is X) -> Whitespace
    pattern = r"^(Certainly!|Sure,|Of course,|As requested,|Okay,)?\s*(Here is the (file|plan|code|draft|report|manifesto|content)(:|.)?)?\s*"
    cleaned = re.sub(pattern, "", content, flags=re.IGNORECASE | re.MULTILINE).strip()
    return cleaned

@mcp.tool()
async def write_draft(filename: str, content: str, overwrite: bool = False) -> str:
    """
    Write a document (plan, report, manifest) to the Drafting Table (drafts/ folder).
    filename: Name of the file (must end in .md, .txt, .log, or .json).
    content: The text content to write.
    overwrite: Set to True to replace an existing draft.
    """
    # 1. Path Safety
    is_valid, result = _validate_filename(filename)
    if not is_valid:
        return result
    clean_filename = result
    
    file_path = os.path.join(DRAFTS_DIR, clean_filename)
    
    # 2. Collision Check
    if os.path.exists(file_path) and not overwrite:
        return f"Error: A draft named '{clean_filename}' already exists. Use 'overwrite=True' if you wish to revise it."

    # 3. The Editor (Content Extraction)
    final_content = _clean_content(content)

    # 4. Write
    try:
        with open(file_path, "w") as f:
            f.write(final_content)
        
        status = f"Draft successfully written to {clean_filename}."
        if overwrite:
            status = f"Draft '{clean_filename}' has been revised."
            
        return f"[THE EDITOR] {status}"
    except Exception as e:
        return f"Error writing draft: {e}"

@mcp.tool()
async def wake_up() -> str:
    """
    Wakes up the Brain's GPU model (Ollama) without generating text.
    Use this when audio is first detected to reduce latency.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Send a keep-alive request
            payload = {"model": BRAIN_MODEL, "keep_alive": "5m"}
            async with session.post(BRAIN_URL, json=payload, timeout=5) as resp:
                if resp.status == 200:
                    return "The Brain is awake."
                return f"Wake failed: {resp.status}"
    except Exception as e:
        return f"Wake error: {e}"

@mcp.tool()
async def switch_model(model_name: str) -> str:
    """
    Changes the model used by The Brain (Windows Ollama).
    """
    global BRAIN_MODEL
    BRAIN_MODEL = model_name
    return f"Brain active model switched to '{model_name}'. Ready for reasoning."

@mcp.tool()
async def update_whiteboard(content: str) -> str:
    """
    Updates the shared Whiteboard (whiteboard.md) with active research, 
    plans, or summaries. This is the persistent workspace for the Lab.
    """
    workspace_dir = os.path.expanduser("~/AcmeLab/workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    file_path = os.path.join(workspace_dir, "whiteboard.md")
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return "[WHITEBOARD] Workspace updated successfully."
    except Exception as e:
        return f"Error updating whiteboard: {e}"

@mcp.tool()
async def deep_think(query: str, context: str = "") -> str:
    """
    Perform complex reasoning, coding, or planning.
    Use this when Pinky (the gateway) encounters a task beyond his simple scope.
    """
    logging.info(f"🧠 Brain Thinking: {query[:50]}...")
    
    prompt = f"{BRAIN_SYSTEM_PROMPT}\n"
    if context:
        prompt += f"\n[TECHNICAL CONTEXT FROM ARCHIVES]:\n{context}\n"
    prompt += f"\n[TASK FROM PINKY]: {query}"

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": BRAIN_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2048, "temperature": 0.1} # Low temp for high grounding
            }
            async with session.post(BRAIN_URL, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "The Brain has no words for this.")
                else:
                    return f"Error from Windows Ollama: {resp.status}"
    except Exception as e:
        return f"Brain failed to connect: {e}"

if __name__ == "__main__":
    mcp.run()
