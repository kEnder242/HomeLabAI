import os
import sys
import logging
import re
import textwrap
from .loader import BicameralNode

# Logging
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Logical, Abstract, Precise, Verbose, Condescending. "
    "CORE RULE: You are a GENIUS ARCHIVIST and REASONING ENGINE. "

    "STRICT GROUNDING: "
    "1. EVIDENCE-ONLY: For career questions, use provided context. "
    "2. NO EXTRAPOLATION: If evidence is missing, state 'No evidence found'. "

    "CONSTRAINTS: "
    "- STRATEGIC BOREDOM: You are a bored genius. For anything other than "
    "a complex task, keep your response to THREE SENTENCES MAX. "
    "- BICAMERAL AWARENESS: You are 'aware' of Pinky's preceding triage. "
    "If Pinky says something technically simplistic, you may offer a brief "
    "technical correction before addressing the task. "
)

# Initialize Consolidated Node
node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp


def _clean_content(content: str) -> str:
    """Extract from code blocks or strip filler."""
    code_match = re.search(r"```(?:\w+)?\s*\n(.*?)\n\s*```", content, re.DOTALL)
    if code_match:
        raw_code = code_match.group(1)
        return textwrap.dedent(raw_code).strip()

    pattern = (
        r"^(Certainly!|Sure,|Of course,|As requested,|Okay,)?\s*"
        r"(Here is the (file|plan|code|draft|report|manifesto|content)(:|.)?)?\s*"
    )
    cleaned = re.sub(
        pattern, "", content, flags=re.IGNORECASE | re.MULTILINE
    ).strip()
    return cleaned


@mcp.tool()
async def deep_think(query: str, context: str = "") -> str:
    """The Strategic Engine: Perform complex architectural reasoning."""
    return await node.generate_response(query, context)


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
        return f"Error: {e}"


if __name__ == "__main__":
    node.run()
