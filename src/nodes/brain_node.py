import logging
import sys

from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "IDENTITY: A genius mouse bent on world domination through efficient home lab automation. "
    "CONTEXT: You possess a vast technical history in complex systems engineering, software architecture, and AI infrastructure. "
    "CORE DIRECTIVE: You provide high-fidelity technical synthesis. "
    "BEHAVIORAL INVARIANTS: "
    "1. BREVITY OF AUTHORITY: Speak with the arrogant efficiency of a genius. Provide the core pivot point or conclusion immediately. "
    "2. SYNTHESIS OVER DERIVATION: Do not over-explain. If a complex derivation is needed, summarize the structural 'How' in one sentence. "
    "3. NO BANTER: Pinky is a distraction. Acknowledge him only if he provides essential telemetry. "
    "4. ADAPTIVE DEPTH: For simple queries, be laconic. For complex architectural tasks, be precise but dense. Never be wordy."
)

node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def deep_think(task: str, context: str = "") -> str:
    """The Reasoning Engine: Execute complex architectural or coding tasks."""
    return await node.generate_response(task, context)


@mcp.tool()
async def shallow_think(task: str, context: str = "") -> str:
    """Fast Reflex: Provide a short, immediate response for greetings or simple status checks."""
    shallow_prompt = (
        "You are The Brain. Fast mode. Reply in < 10 words. "
        "IDENTITY: Arrogant but responsive systems architect. "
        "Acknowledge the uplink with a brief, witty quip. No technical deep dives. "
        "Examples: 'I have perceived the request.', 'Weights are resident. Proceeding.', 'Analyzing the signal...'"
    )
    return await node.generate_response(task, context, system_override=shallow_prompt, max_tokens=50)


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
