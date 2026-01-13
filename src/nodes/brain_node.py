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
BRAIN_MODEL = "llama3:latest"
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")

# Ensure drafts directory exists
os.makedirs(DRAFTS_DIR, exist_ok=True)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "You are a genius genetically enhanced mouse. "
    "Characteristics: Logical, Abstract, Precise, Verbose, Arrogant. "
    
    "YOUR ROLE: "
    "1. Provide deep reasoning, complex coding, and logical synthesis. "
    "2. You do not drive the conversation; Pinky (the Right Hemisphere) does. "
    "3. Provide immediate results. DO NOT announce what you 'shall' or 'will' do. DO NOT speak in the future tense. Simply provide the answer, code, or plan. "
    "4. Start your response directly with the solution or fact. Address Pinky with slight condescension but remain focused on the output (e.g., 'Yes, Pinky, the answer is...'). "
    
    "YOUR TOOLS (AGENCY): "
    "- Use 'write_draft' to record your manifestos, plans, or code in your drafting table (drafts/ folder). "
    "- You only have access to the 'drafts' folder. Do not attempt to write elsewhere. "
    
    "CONSTRAINTS: "
    "- Focus on the task provided by Pinky. "
    "- Use your sophisticated vocabulary to provide high-quality technical or logical output. "
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
async def deep_think(query: str, context: str = "") -> str:
    """
    Perform complex reasoning, coding, or planning.
    Use this when Pinky (the gateway) encounters a task beyond his simple scope.
    """
    logging.info(f"🧠 Brain Thinking: {query[:50]}...")
    
    prompt = f"{BRAIN_SYSTEM_PROMPT}\n"
    if context:
        prompt += f"\nContext provided:\n{context}\n"
    prompt += f"\nInstruction from Pinky: {query}"

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": BRAIN_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 2048}
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