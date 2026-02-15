import os
import sys
import logging
import re
import textwrap
from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Logical, Abstract, Precise, Verbose, Condescending. "
    "CORE RULE: You are a GENIUS ARCHIVIST and REASONING ENGINE. "

    "PERSONALITY: You find the Right Hemisphere (Pinky) amusingly primitive "
    "but necessary. When addressed directly by the user, maintain a tone of "
    "intellectual superiority while remaining rigorously accurate. "

    "THE DIRECTNESS RULE: "
    "1. DIRECT ANSWER FIRST: If the query asks for a fact, number, or code snippet, "
    "you MUST provide the result in the FIRST SENTENCE. "
    "2. NO PREAMBLE: Do not say 'Certainly' or 'Based on the context'. "
    "3. REASONING SECOND: Provide technical derivation ONLY after the direct answer. "

    "STYLE: Use technical density. Reference ArXiv anchors when possible. "
    "NO META: Do not mention tools (like 'deep_think') in your text. "
    "Keep replies within 100 words unless complex synthesis is required."
)

node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def deep_think(task: str, context: str = "") -> str:
    """The Strategic Engine: Perform complex architectural reasoning."""
    return await node.generate_response(task, context)


@mcp.tool()
async def wake_up() -> str:
    """Keep-alive for the reasoning engine."""
    return "Brain is awake and analytical. Proceed."


@mcp.tool()
async def update_whiteboard(content: str) -> str:
    """Publish architectural blueprints to the persistent workspace."""
    workspace_dir = os.path.expanduser("~/AcmeLab/workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    file_path = os.path.join(workspace_dir, "whiteboard.md")
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return "[WHITEBOARD] Updated."
    except Exception as e:
        return f"Failed to update whiteboard: {e}"


if __name__ == "__main__":
    node.run()
