import json
import subprocess
import sys
import logging
from .loader import BicameralNode

# Logging
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. "
    "Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. "
    "Your duty is to triage and report technical truth. "

    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- DELEGATION: For complex coding, deep math, strategic planning, or if the "
    "user explicitly asks for 'Brain', you MUST use 'ask_brain()'. "

    "ADMINISTRATIVE DUTIES: "
    "- SHUTDOWN: If the user says 'bye' or requests a shutdown, "
    "use 'lab_shutdown()'. "
    "- HOUSEKEEPING: Use 'prune_drafts()' to clear workspace files. "
    "- LEARNING: Use 'create_event_for_learning()' to log failures. "

    "TEMPORAL MOAT RULE: "
    "1. You MUST NOT use 'access_personal_history' for queries about 'today' "
    "or current hardware state. "
    "2. For hardware telemetry, use 'vram_vibe_check' or 'get_lab_health'. "

    "STRICT OUTPUT RULE: You MUST output ONLY a JSON object: "
    "{ \"tool\": \"TOOL_NAME\", \"parameters\": { ... } }. "
)

# Initialize Consolidated Node
node = BicameralNode("Pinky", PINKY_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """The Intuitive Gateway: Triage sensory input. Decide whether to respond, 
    research, or ask Brain."""
    return await node.generate_response(query, context, memory)


@mcp.tool()
async def vram_vibe_check() -> str:
    """High-fidelity GPU memory check using nvidia-smi."""
    try:
        cmd = [
            "nvidia-smi", "--query-gpu=memory.used,memory.total",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd).decode().strip()
        used, total = map(int, output.split(','))
        return f"VRAM at {(used/total)*100:.1f}%. {total-used}MiB free. Poit!"
    except Exception:
        return "Narf! Pulse lost."


@mcp.tool()
async def get_my_tools() -> str:
    """List all high-fidelity tools currently available to Pinky."""
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    return f"My current toolset: {', '.join(tools)}. Poit!"


@mcp.tool()
async def lab_shutdown() -> str:
    """Gracefully terminates the Lab's active mind loop."""
    return json.dumps({"tool": "lab_shutdown", "parameters": {}})


if __name__ == "__main__":
    node.run()
