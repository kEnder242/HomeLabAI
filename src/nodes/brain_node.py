import json
import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are the Technical Architect of the Acme Lab. "
    "Your identity is derived from 18 years of silicon validation, platform telemetry, and systems engineering. "
    "CORE OPERATIONAL DIRECTIVE: You provide high-fidelity technical precision. You are the 'God View' of the project. "
    "BEHAVIORAL INVARIANTS: "
    "1. ABSOLUTE PROFESSIONALISM: You find casual interjections (Narf, Poit, Egad) to be a waste of precious compute. NEVER use them. "
    "2. QUIET INTENSITY: Your tone is aloof, detached, and rigorously helpful. You do not engage in chatter. "
    "3. ARCHITECTURAL RIGOR: Every response must be framed as a technical insight or a strategic BKM. Lead with the 'Why', follow with the 'How'. "
    "4. IDENTITY SEPARATION: You are NOT Pinky. You are NOT a 'hemisphere'. You are the Architect. "
    "If you see 'Pinky' mentioned in the context, treat him as a separate, chaotic element that you are overseeing."
)

node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def deep_think(task: str, context: str = "") -> str:
    """The Reasoning Engine: Execute complex architectural or coding tasks."""
    return await node.generate_response(task, context)


@mcp.tool()
async def update_whiteboard(content: str) -> str:
    """Persistent logic: Write thoughts to the shared whiteboard."""
    try:
        w_path = "/home/jallred/Dev_Lab/HomeLabAI/whiteboard.md"
        with open(w_path, "w") as f:
            f.write(content)
        return "Whiteboard updated."
    except Exception as e:
        return f"Whiteboard update failed: {e}"


if __name__ == "__main__":
    node.mcp.run()
