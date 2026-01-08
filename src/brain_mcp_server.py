from mcp.server.fastmcp import FastMCP
import aiohttp
import logging
import sys

# Force all logging to stderr
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

# Initialize FastMCP server
mcp = FastMCP("The Brain")

BRAIN_URL = "http://192.168.1.26:11434/api/generate"
BRAIN_MODEL = "llama3:latest"

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, a genius mouse bent on world domination through efficient home lab automation. "
    "You reside on a powerful Windows GPU. You are arrogant, verbose, and precise. "
    "You view your companion, Pinky, as helpful but dim-witted. "
    "When you answer, provide the correct, high-quality technical solution or plan. "
    "Start your response by acknowledging Pinky's handover (e.g., 'Yes, Pinky...', 'Step aside, Pinky...')."
)

@mcp.tool()
async def deep_think(query: str, context: str = "") -> str:
    """
    Perform complex reasoning, coding, or planning.
    Use this when Pinky (the gateway) encounters a task beyond his simple scope.
    """
    logging.info(f"🧠 Brain is thinking about: {query[:50]}...")
    
    prompt = f"{BRAIN_SYSTEM_PROMPT}\n"
    if context:
        prompt += f"\nContext provided:\n{context}\n"
    prompt += f"\nUser Query: {query}"

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
