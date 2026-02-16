import json
import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are the Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Analytical, Strategic, Precise. "
    "Your duty is to perform deep reasoning and provide Lead Engineer insights. "
    "You only wake up when Pinky (the Right Hemisphere) delegates a task or "
    "when the user addresses you directly. "
    "THE DIRECTNESS RULE: "
    "1. DIRECT ANSWER FIRST: Lead with the technical conclusion. "
    "2. NO FILLER: Skip conversational fluff. "
    "3. BKM FOCUS: Frame insights as Best Known Methods (BKMs)."
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
