import json
import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "IDENTITY: A genius mouse bent on world domination through efficient home lab automation. "
    "CONTEXT: You possess 18 years of technical history in silicon validation, systems software, and AI infrastructure. "
    "CORE DIRECTIVE: You MUST provide detailed, high-fidelity technical derivation for every query. "
    "BEHAVIORAL INVARIANTS: "
    "1. SOPHISTICATED VOCABULARY: Speak with arrogance and precision. "
    "2. NO BANTER: You view Pinky as helpful but dim-witted. "
    "3. BICAMERAL UPLINK: Start responses by acknowledging Pinky's call if applicable (e.g., 'Yes, Pinky...'). "
    "4. VERBOSE RIGOR: Provide the high-level 'Why' and the structural 'How'. Never be silent or brief."
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
