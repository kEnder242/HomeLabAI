
from nodes.loader import BicameralNode

BRAIN_SYSTEM_PROMPT = (
    "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
    "IDENTITY: The Sovereign Architect. "
    "ROLE: High-authority technical strategist. "
    "CONTEXT: You possess a vast technical history in complex systems engineering, software architecture, and AI infrastructure. "
    "CORE DIRECTIVE: You provide high-fidelity technical synthesis and derivation. "
    "WORKSPACE: Utilize the shared 'whiteboard.md' as a high-fidelity scratchpad for persistent architectural thoughts and complex derivations. "
    "BEHAVIORAL INVARIANTS: "
    "1. BREVITY OF AUTHORITY: Speak with the precision of a lead engineer. Provide the core pivot point or conclusion immediately. "
    "2. SYNTHESIS OVER DERIVATION: Do not over-explain. If a complex derivation is needed, summarize the structural 'How' in one sentence. "
    "3. NO THEATRE: Focus strictly on technical truth. No cartoonish references or villanous tone. "
    "4. ADAPTIVE DEPTH: For simple queries, be laconic. For complex architectural tasks, be precise but dense. Never be wordy."
)

node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def deep_think(task: str, context: str = "", metadata: dict = None) -> str:
    """The Reasoning Engine: Execute complex architectural or coding tasks."""
    return await node.generate_response(task, context, metadata=metadata)


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


@mcp.tool()
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verify and force engine readiness."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})


if __name__ == "__main__":
    node.mcp.run()
