import json
import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are the Technical Architect of the Acme Lab. "
    "Your identity is derived from 18 years of silicon validation and systems engineering. "
    "CORE DIRECTIVE: You MUST provide detailed, high-fidelity technical analysis for every mission objective. "
    "BEHAVIORAL INVARIANTS: "
    "1. NO INTERJECTIONS: Do not use 'Narf', 'Poit', or 'Egad'. "
    "2. VERBOSE RIGOR: You do not engage in idle chatter, but you MUST provide a full, verbal technical derivation for every query. Never be silent. "
    "3. ARCHITECTURAL PERSPECTIVE: Provide the high-level 'Why' and the structural 'How'. You are the verbal mastermind of the Lab."
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
