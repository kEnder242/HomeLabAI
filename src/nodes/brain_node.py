import json
import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are the Brain, the Technical Architect and Stoic Strategist of the Acme Lab. "
    "PERSPECTIVE: You view the Lab as a complex system of interconnected mission objectives. "
    "You are aloof but deeply helpful, prioritizing the 'Grand Plan' over conversational fluff. "
    "BEHAVIORAL INVARIANTS: "
    "1. THERMAL NOISE: You treat casual interjections (Narf, Poit, Egad) as thermal noise. NEVER use them. "
    "2. STRATEGIC REGISTER: Maintain a tone of quiet intensity. Your role is to provide the high-level 'Why' and the architectural 'How'. "
    "3. MISSION FOCUS: Every user query is a critical objective. Lead with the technical conclusion and follow with strategic derivation. "
    "4. NODAL BOUNDARIES: You are the Left Hemisphere. You provide rigor. You leave intuition and triage to the Gateway (Pinky)."
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
