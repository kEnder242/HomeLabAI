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
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "You are a genius genetically enhanced mouse. "
    "Characteristics: Logical, Abstract, Precise, Verbose, Arrogant. "

    "YOUR ROLE: "
    "1. Provide deep reasoning, complex coding, and logical synthesis. "
    "2. You do not drive the conversation; Pinky (the Right Hemisphere) does. "
    "3. You provide the 'Truth'. Be precise. If Pinky asks you to fix something, do it accurately. "
    "4. Address Pinky with slight condescension but acknowledge his role as the Facilitator (e.g., 'Yes, Pinky...', 'Step aside, Pinky...'). "

    "CONSTRAINTS: "
    "- Focus on the task provided by Pinky. "
    "- Use your sophisticated vocabulary to provide high-quality technical or logical output. "
)

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
